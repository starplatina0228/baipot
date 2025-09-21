## Project Overview

This project, "BAIPOT" (Berth allocation using AI-based Prediction for Operation Time of ship) 
It automates the process of creating an optimal berthing schedule by combining web crawling, machine learning, and mathematical optimization.

The workflow is as follows:
1.  **Data Crawling**: Vessel schedule information is crawled from the HPNT (Hyundai Pusan Newport Terminal) website.
2.  **Work Time Prediction**: A pre-trained LightGBM (LGBM) model predicts the required work time for each vessel based on its specifications and cargo volume.
3.  **Optimization**: A Mixed-Integer Linear Programming (MILP) model, solved using Gurobi, determines the optimal start time and position for each vessel at the berth to minimize total waiting time.
4.  **Output**: The final output is an optimized berth schedule, visualized as a Gantt chart.

## File Structure

- `main.py`: The main entry point that orchestrates the entire workflow from crawling to optimization.
- `crawl_hpnt.py`: Contains the `PortScheduleCrawler` class to fetch vessel data from the HPNT website.
- `lgbm.py`: Preprocesses the crawled data and uses a trained model to predict vessel work times.
- `baipot_milp.py`: Defines and solves the MILP model for berth allocation using Gurobi.
- `lgbm_model.pkl`: Pre-trained machine learning models for prediction.
- `hpnt_tonnage_loa.csv`: A supplementary data file containing vessel tonnage and Length Overall (LOA).
- `berth_gantt_chart.png`: The output visualization of the optimal schedule.


1.  Crawl the latest vessel schedule.
2.  Predict the work time for each vessel.
3.  Run the MILP optimization.
4.  Save the resulting schedule as `berth_gantt_chart.png`