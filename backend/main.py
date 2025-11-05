from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import date, datetime, timedelta
from typing import List
import pandas as pd
import numpy as np
import json
import asyncio
import threading

from crawling import get_work_plan_data
from prediction import predict_work_time
from optimization import run_milp_model

app = FastAPI(
    title="Berth Allocation and Prediction Optimization (BAIPOT) API",
    description="API for running berth optimization, managing ship data, and viewing results.",
    version="0.1.0",
)

# CORS Middleware
origins = [
    "http://localhost:5173",
    "https://choi.github.io/baipot",
    " https://7d537719c0f4.ngrok-free.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request bodies
class CrawlRequest(BaseModel):
    start_date: date = Field(..., description="Crawling start date in YYYY-MM-DD format.", example="2025-10-01")
    end_date: date = Field(..., description="Crawling end date in YYYY-MM-DD format.", example="2025-10-10")

class OptimizeSelectedRequest(CrawlRequest):
    selected_ships: List[str] = Field(..., description="List of merge_keys for the ships to be optimized.")

class EtdRequest(BaseModel):
    ship_name: str = Field(..., example="GEMINI")
    eta: datetime = Field(..., description="Estimated Time of Arrival in ISO format.")
    cargo_load: int = Field(..., example=100)
    cargo_unload: int = Field(..., example=100)
    ship_length: float = Field(..., example=150.0)
    shipping_company: str = Field(..., example="GGL")
    gross_tonnage: float = Field(..., example=50000.0)
    shift: int = Field(..., example=0)


async def _get_prepared_data(request: CrawlRequest) -> pd.DataFrame:
    """Helper function to crawl and prepare data, returning a DataFrame."""
    try:
        start_str = request.start_date.strftime('%Y-%m-%d')
        end_str = request.end_date.strftime('%Y-%m-%d')
        
        crawled_data = get_work_plan_data(
            start_date=start_str,
            end_date=end_str,
            output_format='json'
        )
        
        if not crawled_data or not crawled_data.get('schedule_data'):
            # Return empty dataframe if no data is crawled
            return pd.DataFrame()

        crawled_df = pd.DataFrame(crawled_data['schedule_data'])
        crawled_df.drop_duplicates(subset=['선사', '선명', '모선항차', '선사항차'], inplace=True)
        final_df = predict_work_time(crawled_df)
        return final_df
    except Exception as e:
        # Re-raise exceptions to be handled by the calling endpoint
        raise e

async def _run_optimization_cancellable(request: Request, data_to_optimize: pd.DataFrame, fixed_ship_merge_keys: List[str] = None):
    """Runs the optimization in a thread with cancellation support."""
    cancel_event = threading.Event()
    disconnect_checker_task = None

    async def _check_disconnect():
        while not await request.is_disconnected():
            await asyncio.sleep(0.1)
        print("Client disconnected, setting cancel event.")
        cancel_event.set()

    try:
        disconnect_checker_task = asyncio.create_task(_check_disconnect())
        
        optimized_df = await asyncio.to_thread(
            run_milp_model, data_to_optimize, cancel_event, fixed_ship_merge_keys
        )

        return optimized_df
    finally:
        if disconnect_checker_task:
            disconnect_checker_task.cancel()

@app.get("/")
def read_root():
    """
    Root endpoint for the API.
    """
    return {"message": "Welcome to the BAIPOT API"}

@app.get("/ships")
def get_ships():
    """
    Returns a list of all ships from the ship_info.csv file.
    """
    try:
        ship_info_df = pd.read_csv('ship_info.csv')
        ship_info_df = ship_info_df.replace({np.nan: None})
        result_json = ship_info_df.to_json(orient='records')
        return json.loads(result_json)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="ship_info.csv not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while reading ship_info.csv: {str(e)}")

@app.post("/schedule/prepare")
async def prepare_schedule_data(request: CrawlRequest):
    """
    Crawls ship data, enriches it, predicts work time, and returns the data table.
    """
    try:
        final_df = await _get_prepared_data(request)
        if final_df.empty:
            return []
        
        # Replace NaN/NaT with None and convert to JSON
        final_df = final_df.replace({pd.NaT: None, np.nan: None})
        result_json = final_df.to_json(orient='records', date_format='iso')
        
        return json.loads(result_json)

    except ValueError as ve:
        raise HTTPException(status_code=500, detail=f"Data processing or prediction failed: {str(ve)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during schedule preparation: {str(e)}")

@app.post("/schedule/calculate-etd")
async def calculate_etd(etd_request: EtdRequest, request: Request):
    """
    Calculates the ETD for a single ship based on its ETA and other details.
    """
    try:
        # 1. Create a DataFrame for the new ship
        new_ship_data = {
            '선명': etd_request.ship_name,
            '선사': etd_request.shipping_company,
            '모선항차': '',
            '접안예정일시': etd_request.eta.strftime('%Y-%m-%d %H:%M'),
            '양하': str(etd_request.cargo_unload),
            '적하': str(etd_request.cargo_load),
            'LOA': etd_request.ship_length,
            '총톤수': etd_request.gross_tonnage,
            'Shift': str(etd_request.shift),
            '선사항차': '', '항로': '', '반입마감시한': '', '출항예정일시': '',
            'AMP': '', '상태': 'PLANNED', '선석': ''
        }
        new_ship_df = pd.DataFrame([new_ship_data])
        new_ship_df['접안예정일시'] = pd.to_datetime(new_ship_df['접안예정일시'])

        # 2. Predict work time for the new ship
        # Note: predict_work_time will fill missing LOA/총톤수 for crawled data,
        # but for a new ship, these must be provided.
        new_ship_df = predict_work_time(new_ship_df)
        new_ship_merge_key = f"{etd_request.shipping_company}_{etd_request.ship_name.replace(' ', '')}"
        new_ship_df['merge_key'] = new_ship_merge_key

        # 3. Get existing schedule around the new ship's ETA
        eta = etd_request.eta
        start_date = (eta - timedelta(days=1)).date()
        end_date = (eta + timedelta(days=1)).date()
        
        crawl_req = CrawlRequest(start_date=start_date, end_date=end_date)
        existing_df = await _get_prepared_data(crawl_req)

        fixed_ship_merge_keys = []
        if not existing_df.empty:
            existing_df['merge_key'] = existing_df['선사'].astype(str) + '_' + existing_df['선명'].str.replace(r'\s+', '', regex=True)
            # Only fix ships that are already arrived.
            fixed_statuses = ['ARRIVED'] 
            fixed_ships_df = existing_df[existing_df['상태'].isin(fixed_statuses)]
            fixed_ship_merge_keys = fixed_ships_df['merge_key'].tolist()

        # 4. Combine dataframes
        combined_df = pd.concat([existing_df, new_ship_df], ignore_index=True)

        # 5. Run optimization
        optimized_df = await _run_optimization_cancellable(request, combined_df, fixed_ship_merge_keys)

        if optimized_df is None:
            raise HTTPException(status_code=500, detail="Optimization failed to find a schedule for the new ship.")

        # 6. Return the entire optimized schedule
        start_time_ref = combined_df['접안예정일시'].min()

        # Add Start_dt and Completion_dt to the entire dataframe
        optimized_df['Start_dt'] = optimized_df['Start_h'].apply(lambda h: start_time_ref + timedelta(hours=h))
        optimized_df['Completion_dt'] = optimized_df['Completion_h'].apply(lambda h: start_time_ref + timedelta(hours=h))

        # Replace NaN/NaT with None and convert to JSON
        optimized_df = optimized_df.replace({pd.NaT: None, np.nan: None})
        result_json = optimized_df.to_json(orient='records', date_format='iso')
        
        return json.loads(result_json)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"An error occurred during ETD calculation: {str(e)}")

@app.post("/schedule/optimize")
async def optimize_schedule(crawl_request: CrawlRequest, request: Request):
    """
    Runs the full pipeline: crawl, predict, and optimize the berth schedule.
    """
    try:
        prepared_df = await _get_prepared_data(crawl_request)
        
        if prepared_df.empty:
            raise HTTPException(status_code=404, detail="No data available to optimize.")

        optimized_df = await _run_optimization_cancellable(request, prepared_df)

        if optimized_df is None:
            # This can mean optimization failed, was infeasible, or was cancelled.
            raise HTTPException(status_code=500, detail="Optimization failed, was infeasible, or was cancelled by the user.")

        start_time_ref = prepared_df['접안예정일시'].min()
        optimized_df['Start_dt'] = optimized_df['Start_h'].apply(lambda h: start_time_ref + timedelta(hours=h))
        optimized_df['Completion_dt'] = optimized_df['Completion_h'].apply(lambda h: start_time_ref + timedelta(hours=h))

        optimized_df = optimized_df.replace({pd.NaT: None, np.nan: None})
        result_json = optimized_df.to_json(orient='records', date_format='iso')
        
        return json.loads(result_json)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during optimization: {str(e)}")

@app.post("/schedule/optimize-selected")
async def optimize_selected_schedule(optimize_request: OptimizeSelectedRequest, request: Request):
    """
    Runs the optimization for a selection of ships.
    """
    try:
        prepared_df = await _get_prepared_data(optimize_request)
        
        if prepared_df.empty:
            raise HTTPException(status_code=404, detail="No data available to optimize.")

        prepared_df['merge_key'] = prepared_df['선사'].astype(str) + '_' + prepared_df['선명'].str.replace(r'\s+', '', regex=True)

        selected_df = prepared_df[prepared_df['merge_key'].isin(optimize_request.selected_ships)]

        if selected_df.empty:
            raise HTTPException(status_code=404, detail="None of the selected ships were found in the data for the given period.")

        optimized_df = await _run_optimization_cancellable(request, selected_df)

        if optimized_df is None:
            raise HTTPException(status_code=500, detail="Optimization failed, was infeasible, or was cancelled by the user.")

        start_time_ref = prepared_df['접안예정일시'].min()
        optimized_df['Start_dt'] = optimized_df['Start_h'].apply(lambda h: start_time_ref + timedelta(hours=h))
        optimized_df['Completion_dt'] = optimized_df['Completion_h'].apply(lambda h: start_time_ref + timedelta(hours=h))

        optimized_df = optimized_df.replace({pd.NaT: None, np.nan: None})
        result_json = optimized_df.to_json(orient='records', date_format='iso')
        
        return json.loads(result_json)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during selective optimization: {str(e)}")