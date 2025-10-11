from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import date
from typing import List
import pandas as pd
import numpy as np
import json

from .crawling import get_work_plan_data
from .prediction import predict_work_time
from .optimization import run_milp_model

app = FastAPI(
    title="Berth Allocation and Prediction Optimization (BAIPOT) API",
    description="API for running berth optimization, managing ship data, and viewing results.",
    version="0.1.0",
)

# CORS Middleware
origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
            raise HTTPException(status_code=404, detail="No data could be crawled for the given period.")

        crawled_df = pd.DataFrame(crawled_data['schedule_data'])
        final_df = predict_work_time(crawled_df)
        return final_df
    except Exception as e:
        # Re-raise exceptions to be handled by the calling endpoint
        raise e

@app.get("/")
def read_root():
    """
    Root endpoint for the API.
    """
    return {"message": "Welcome to the BAIPOT API"}

@app.post("/schedule/prepare")
async def prepare_schedule_data(request: CrawlRequest):
    """
    Crawls ship data, enriches it, predicts work time, and returns the data table.
    """
    try:
        final_df = await _get_prepared_data(request)
        
        # Replace NaN/NaT with None and convert to JSON
        final_df = final_df.replace({pd.NaT: None, np.nan: None})
        result_json = final_df.to_json(orient='records', date_format='iso')
        
        return json.loads(result_json)

    except ValueError as ve:
        raise HTTPException(status_code=500, detail=f"Data processing or prediction failed: {str(ve)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during schedule preparation: {str(e)}")

@app.post("/schedule/optimize")
async def optimize_schedule(request: CrawlRequest):
    """
    Runs the full pipeline: crawl, predict, and optimize the berth schedule.
    """
    try:
        # Step 1 & 2: Get the prepared and predicted data
        prepared_df = await _get_prepared_data(request)
        
        if prepared_df.empty:
            raise HTTPException(status_code=404, detail="No data available to optimize.")

        # Step 3: Run the optimization
        optimized_df = run_milp_model(prepared_df)

        if optimized_df is None:
            raise HTTPException(status_code=500, detail="Optimization failed to find a solution. The problem may be infeasible.")

        # Step 4: Convert and return the optimization result
        optimized_df = optimized_df.replace({pd.NaT: None, np.nan: None})
        result_json = optimized_df.to_json(orient='records', date_format='iso')
        
        return json.loads(result_json)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during optimization: {str(e)}")

@app.post("/schedule/optimize-selected")
async def optimize_selected_schedule(request: OptimizeSelectedRequest):
    """
    Runs the optimization for a selection of ships.
    """
    try:
        # Step 1 & 2: Get the prepared and predicted data
        prepared_df = await _get_prepared_data(request)
        
        if prepared_df.empty:
            raise HTTPException(status_code=404, detail="No data available to optimize.")

        # Create the merge_key in the prepared_df to filter against
        prepared_df['merge_key'] = prepared_df['선사'].astype(str) + '_' + prepared_df['선명'].str.replace(r'\s+', '', regex=True)

        # Filter the DataFrame to include only the selected ships
        selected_df = prepared_df[prepared_df['merge_key'].isin(request.selected_ships)]

        if selected_df.empty:
            raise HTTPException(status_code=404, detail="None of the selected ships were found in the data for the given period.")

        # Step 3: Run the optimization on the filtered data
        optimized_df = run_milp_model(selected_df)

        if optimized_df is None:
            raise HTTPException(status_code=500, detail="Optimization failed to find a solution for the selected ships.")

        # Step 4: Convert and return the optimization result
        optimized_df = optimized_df.replace({pd.NaT: None, np.nan: None})
        result_json = optimized_df.to_json(orient='records', date_format='iso')
        
        return json.loads(result_json)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during selective optimization: {str(e)}")