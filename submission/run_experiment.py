import time
import pandas as pd
from utils import predict_work_time, run_milp_model
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# Matplotlib 기본 설정 (한글 폰트가 없는 경우 깨질 수 있습니다)
# 깨지는 경우, 나눔고딕 등 설치된 폰트 이름으로 변경해주세요.
plt.rcParams['font.family'] = 'sans-serif' 
plt.rcParams['axes.unicode_minus'] = False


def draw_gantt_chart(ax, df, title, start_col, end_col, color_map, xlim_min, xlim_max, is_baipot=False):
    """지정된 축(ax)에 간트 차트를 그립니다."""
    
    df = df.copy()
    df[start_col] = pd.to_datetime(df[start_col])
    df[end_col] = pd.to_datetime(df[end_col])
    df['duration'] = df[end_col] - df[start_col]

    # BAIPOT 차트 (연속적인 Quay 위치)
    if is_baipot:
        ax.set_ylabel("Quay Position (m)")
        ax.set_ylim(0, 1150) # 안벽 총 길이에 맞게 조정 가능
        for _, task in df.iterrows():
            ship_color = color_map.get(task['선명'], '#808080') # 없으면 회색
            
            # Draw buffer
            buffer_start = task[start_col] - timedelta(hours=1)
            buffer_duration = task['duration'] + timedelta(hours=2)
            ax.barh(y=task['Position_m'], width=buffer_duration, left=buffer_start,
                    height=task['Length_m'], align='edge', color='blue', alpha=0.5, edgecolor='blue')

            # 선박 길이(Height)와 위치(Y)를 이용해 사각형을 그림
            ax.barh(y=task['Position_m'], width=task['duration'], left=task[start_col], 
                    height=task['Length_m'], align='edge', edgecolor='black', alpha=0.8, color=ship_color)
            
            # 사각형 중앙에 선박명 텍스트 표시
            ax.text(task[start_col] + task['duration'] / 2, task['Position_m'] + task['Length_m'] / 2, 
                    task['선명'], ha='center', va='center', color='black', fontsize=8, fontweight='bold')
    
    # HPNT 차트 (이산적인 선석)
    else:
        berth_col = '선석'
        y_labels = sorted(df[berth_col].dropna().unique(), key=lambda x: str(x))
        y_pos = {berth: i for i, berth in enumerate(y_labels)}
        
        ax.set_yticks(list(y_pos.values()))
        ax.set_yticklabels(list(y_pos.keys()))
        ax.set_ylim(-0.5, len(y_labels) - 0.5)
        ax.set_ylabel("Berth")

        for _, task in df.iterrows():
            if pd.notna(task[berth_col]):
                berth_y_pos = y_pos[task[berth_col]]
                ship_color = color_map.get(task['선명'], '#808080')
                ax.barh(berth_y_pos, task['duration'], left=task[start_col], height=0.6, align='center', edgecolor='black', color=ship_color)
                ax.text(task[start_col] + task['duration'] / 2, berth_y_pos, task['선명'], 
                        ha='center', va='center', color='black', fontsize=8, fontweight='bold')

    # 공통 포맷팅
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=10, maxticks=20))
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Time")
    ax.grid(True, which='major', axis='x', linestyle='--')
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_xlim(xlim_min, xlim_max) # X축 동기화

def plot_gantt_charts_for_date(work_plan_df, solution_df, date_str):
    """원본 데이터와 최적화 결과를 비교하는 간트 차트를 생성하고 저장합니다."""
    
    print("\n--- Generating Gantt chart ---")
    
    # 1. 고유 선박에 대한 색상 맵 생성
    all_ships = pd.concat([work_plan_df['선명'], solution_df['선명']]).unique()
    # tab20 colormap은 20개의 색상을 제공합니다. 선박이 더 많으면 색이 반복될 수 있습니다.
    colors = plt.cm.get_cmap('tab20', len(all_ships))
    color_map = {ship: colors(i) for i, ship in enumerate(all_ships)}

    # 2. X축 시간 범위 동기화를 위한 전체 시간 범위 계산
    min_time_hpnt = pd.to_datetime(work_plan_df['접안예정일시']).min()
    max_time_hpnt = pd.to_datetime(work_plan_df['출항예정일시']).max()
    min_time_baipot = pd.to_datetime(solution_df['Start_Time']).min()
    max_time_baipot = pd.to_datetime(solution_df['ETD']).max()

    overall_min_time = min(min_time_hpnt, min_time_baipot)
    overall_max_time = max(max_time_hpnt, max_time_baipot)

    # 시간 축에 여백 추가
    time_padding = timedelta(hours=3)
    overall_min_time -= time_padding
    overall_max_time += time_padding

    # 3. 차트 그리기
    fig, axes = plt.subplots(2, 1, figsize=(20, 14), constrained_layout=True)
    fig.suptitle(f'Berth Allocation Plan Comparison ({date_str})', fontsize=18, fontweight='bold')

    # 상단: HPNT 원본 데이터 간트 차트
    draw_gantt_chart(axes[0], work_plan_df, "HPNT Berth Plan", '접안예정일시', '출항예정일시', color_map, overall_min_time, overall_max_time, is_baipot=False)

    # 하단: BAIPOT 최적화 결과 간트 차트
    # '선명' 컬럼이 없을 경우를 대비하여 rename
    if '선명' not in solution_df.columns and 'Ship' in solution_df.columns:
        solution_df.rename(columns={'Ship': '선명'}, inplace=True)
    draw_gantt_chart(axes[1], solution_df, "BAIPOT Berth Plan", 'Start_Time', 'ETD', color_map, overall_min_time, overall_max_time, is_baipot=True)

    # 4. 파일로 저장
    output_dir = f"results_{date_str}"
    output_filename = f"gantt_comparison_{date_str}.png"
    output_path = os.path.join(output_dir, output_filename)
    plt.savefig(output_path)
    print(f"Success: Comparison chart saved to '{output_path}'.")
    plt.close(fig)


def compare_etd(solution_df_with_all_info, output_path):
    """모든 정보가 포함된 DataFrame을 받아 ETD 비교 CSV 파일로 저장합니다."""
    desired_columns = ['Ship', '선사', '모선항차', '선사항차', '접안예정일시', '출항예정일시', 'ETD']
    columns_to_include = [col for col in desired_columns if col in solution_df_with_all_info.columns]
    comparison_df = solution_df_with_all_info[columns_to_include]
    
    print("\n--- ETD Comparison ---")
    print(comparison_df)
    comparison_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"ETD comparison results saved to {output_path}")


def run_experiment_for_date(date_str):
    """지정된 날짜의 데이터를 사용하여 BAP 실험을 수행하고, 결과를 CSV와 간트차트로 저장합니다."""
    print(f"--- Running Experiment for {date_str} ---")

    # 1. 크롤링된 데이터 파일 읽기
    output_dir = f"results_{date_str}"
    crawled_data_filename = f"hpnt_crawled_data_{date_str}.csv"
    crawled_data_path = os.path.join(output_dir, crawled_data_filename)

    if not os.path.exists(crawled_data_path):
        print(f"Crawled data file not found: {crawled_data_path}")
        return

    work_plan_df = pd.read_csv(crawled_data_path)
    print(f"Successfully loaded {len(work_plan_df)} records from {crawled_data_path}")

    # ship_info.csv에서 총톤수, LOA 정보 병합
    ship_info_df = pd.read_csv('ship_info.csv')
    ship_info_df['merge_key'] = ship_info_df['선사'].astype(str) + '_' + ship_info_df['선명'].str.replace(r'\s+', '', regex=True)
    ship_info_df.drop_duplicates(subset=['merge_key'], inplace=True)
    
    work_plan_df['merge_key'] = work_plan_df['선사'].astype(str) + '_' + work_plan_df['선명'].str.replace(r'\s+', '', regex=True)
    
    work_plan_df = pd.merge(work_plan_df, ship_info_df[['merge_key', '총톤수', 'LOA']], on='merge_key', how='left')
    work_plan_df.drop(columns=['merge_key'], inplace=True)

    # 정보가 없는 선박에 대해 평균값으로 대체
    missing_info_rows = work_plan_df[work_plan_df['총톤수'].isnull() | work_plan_df['LOA'].isnull()]
    if not missing_info_rows.empty:
        print("일부 선박의 '총톤수' 또는 'LOA' 정보가 없어 평균값으로 대체합니다.")
        work_plan_df['총톤수'].fillna(work_plan_df['총톤수'].mean(), inplace=True)
        work_plan_df['LOA'].fillna(work_plan_df['LOA'].mean(), inplace=True)

    # 2. 작업 소요 시간 예측
    print("\n--- Predicting Work Time ---")
    predicted_df = predict_work_time(work_plan_df.copy())

    if 'predicted_work_time' not in predicted_df.columns:
        print("'predicted_work_time' column not found. Exiting.")
        return

    # 3. MILP 최적화 실행
    print("\n--- Optimizing with MILP model ---")
    try:
        start_time = time.time()
        solution_df_results_only = run_milp_model(predicted_df)
        end_time = time.time()
        print(f"Computation time: {end_time - start_time:.2f} sec")

        if solution_df_results_only is not None and not solution_df_results_only.empty:
            
            # 4. ★★★ 핵심: MILP 결과와 원본 정보를 병합하여 모든 컬럼 유지 ★★★
            solution_df = pd.merge(
                solution_df_results_only, 
                predicted_df, 
                left_on=['Ship', '모선항차'], 
                right_on=['선명', '모선항차'], 
                how='left'
            )

            # 5. 시간 관련 컬럼 계산 (시각화 및 CSV 저장용)
            start_time_ref = pd.to_datetime(predicted_df['접안예정일시'].min())
            
            # Plotting을 위한 datetime 객체 컬럼
            solution_df['Start_Time'] = start_time_ref + pd.to_timedelta(solution_df['Start_h'], unit='h')
            solution_df['ETD_datetime'] = start_time_ref + pd.to_timedelta(solution_df['Completion_h'], unit='h')
            solution_df.rename(columns={'ETD_datetime': 'ETD'}, inplace=True) # 컬럼 이름 통일

            # 6. 간트 차트 생성 및 저장
            # 시각화 함수는 datetime 객체를 사용
            plot_gantt_charts_for_date(work_plan_df, solution_df.copy(), date_str)

            # 7. ETD 비교 CSV 파일 저장
            # CSV 저장을 위해 ETD 컬럼을 문자열로 변환
            solution_df_for_csv = solution_df.copy()
            solution_df_for_csv['ETD'] = solution_df_for_csv['ETD'].dt.strftime('%Y-%m-%d %H:%M')
            etd_comparison_filename = f"etd_comparison_{date_str}.csv"
            etd_comparison_path = os.path.join(output_dir, etd_comparison_filename)
            compare_etd(solution_df_for_csv, etd_comparison_path)
        
        else:
            print("MILP solver did not return a valid solution.")

    except Exception as e:
        print(f"An error occurred during processing: {e}")

if __name__ == '__main__':
    dates_to_run = [
        "20251030",
        "20251031", 
        "20251101",
        "20251102",
        "20251103",
        "20251104"
    ]
    
    for date_str in dates_to_run:
        if os.path.isdir('results_' + date_str):
            run_experiment_for_date(date_str)
        else:
            print(f"Directory for date {date_str} not found, skipping.")
        print("\n" + "="*50 + "\n")