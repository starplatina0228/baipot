import pandas as pd
import glob
import os
import numpy as np

print("ETD 예측 오차 분석을 시작합니다 (최종 항차별 분석 버전)...")

# --- 설정 ---
# 분석할 시간 윈도우 (일)
time_windows = [3, 5, 7, 10]
# 결과물을 저장할 폴더
output_folder = 'analysis_results_fixed_target'
# 전처리된 데이터가 있는 기본 폴더
processed_base_folder = 'scenario_fixed_target_processed'

# 출력 폴더 생성
os.makedirs(output_folder, exist_ok=True)

# --- 각 Time Window 별로 분석 루프 실행 ---
for window in time_windows:
    print(f"\n{'='*20} {window}일 윈도우 분석 시작 {'='*20}")

    # 1. 해당 Window의 모든 전처리된 파일 읽기
    processed_folder_path = os.path.join(processed_base_folder, f'{window}days')

    all_files = glob.glob(os.path.join(processed_folder_path, '*.csv'))
    if not all_files:
        print(f"경고: {processed_folder_path} 폴더에 CSV 파일이 없습니다.")
        print(f"data_preprocess.py를 먼저 실행했는지 확인하세요.")
        continue

    df_list = []
    for f in all_files:
        try:
            df_temp = pd.read_csv(f, dtype={'모선항차': str, '선사항차': str})
            df_list.append(df_temp)
        except Exception as e:
            print(f"에러: {f} 파일을 읽는 중 오류 발생 - {e}")
            continue

    if not df_list:
        print(f"에러: {window}일 윈도우에 대한 데이터를 읽을 수 없습니다.")
        continue

    df_window = pd.concat(df_list, ignore_index=True)

    # 2. 데이터 전처리
    # 날짜/시간 컬럼 타입 변환
    df_window['호출일'] = pd.to_datetime(df_window['호출일'], errors='coerce')
    df_window['출항예정일시'] = pd.to_datetime(df_window['출항예정일시'], errors='coerce')
    df_window['ETD'] = pd.to_datetime(df_window['ETD'], errors='coerce')

    # 분석에 필수적인 데이터가 없는 행 제거
    df_window.dropna(subset=['호출일', '출항예정일시', 'Ship', '모선항차', '선사항차', 'ETD', '시간차이(시)'], inplace=True)

    # '선박명' + '모선항차' + '선사항차'를 조합하여 고유한 항차 ID 생성
    df_window['Voyage_ID'] = df_window['Ship'].astype(str) + '_' + \
                             df_window['모선항차'].astype(str) + '_' + \
                             df_window['선사항차'].astype(str)

    # 실제 예측이 이루어진 시점 계산 (출항예정일시 D-day 기준)
    time_delta = df_window['출항예정일시'] - df_window['호출일']
    df_window['실제_예측_시점'] = np.ceil(time_delta.dt.total_seconds() / (24 * 3600)).astype(int)

    # 해당 윈도우 범위 내의 예측 데이터만 필터링
    df_window = df_window[(df_window['실제_예측_시점'] <= window) & (df_window['실제_예측_시점'] > 0)]

    if df_window.empty:
        print(f"분석할 데이터가 없습니다. 다음 윈도우로 넘어갑니다.")
        continue

    # 3. 결과 저장할 하위 폴더 생성
    output_subfolder = os.path.join(output_folder, f'fixed_target_{window}days_window')
    os.makedirs(output_subfolder, exist_ok=True)

    # 4. 실험 1: 예측 시점별 전체 오차 요약 (MAE)
    error_summary = df_window.groupby('실제_예측_시점').agg(
        MAE=('시간차이(시)', 'mean'),      # 절대 오차의 평균
        Count=('Voyage_ID', 'count')     # 데이터 수
    ).reset_index()
    error_summary.rename(columns={'MAE': '평균_절대_오차(MAE)', 'Count': '데이터_수'}, inplace=True)

    full_day_range = pd.DataFrame({'실제_예측_시점': range(1, window + 1)})
    final_summary_table = pd.merge(full_day_range, error_summary, on='실제_예측_시점', how='left').fillna(0)
    final_summary_table['데이터_수'] = final_summary_table['데이터_수'].astype(int)
    final_summary_table = final_summary_table.round(2).sort_values(by='실제_예측_시점', ascending=False)

    summary_output_path = os.path.join(output_subfolder, 'summary_errors_by_calling_point.csv')
    final_summary_table.to_csv(summary_output_path, index=False, encoding='utf-8-sig')

    print(f"\n[{window}일 윈도우] 호출 시점별 오차 요약 (MAE):")
    print(final_summary_table.to_string(index=False))
    print(f" >> '{summary_output_path}' 에 저장 완료")

    # 전체 기간에 대한 평균 오차 계산 및 출력
    overall_mae = df_window['시간차이(시)'].mean()

    print(f"\n[{window}일 윈도우] 전체 평균 오차:")
    print(f"  - 전체 평균 절대 오차 (MAE): {overall_mae:.2f} 시간")

    # 5. 실험 2: '항차(Voyage)'별 오차 추적 데이터 저장 및 출력
    analysis_df = df_window.sort_values('호출일', ascending=True).drop_duplicates(subset=['Voyage_ID', '실제_예측_시점'], keep='last')
    analysis_df = analysis_df.sort_values(by=['Voyage_ID', '실제_예측_시점'], ascending=[True, False])

    result_cols = ['Ship', '모선항차', '선사항차', '실제_예측_시점', '접안예정일시', 'ETD', '출항예정일시', '시간차이(시)', '호출일']

    ship_output_path = os.path.join(output_subfolder, 'analysis_by_voyage.csv')
    analysis_df[result_cols].to_csv(ship_output_path, index=False, encoding='utf-8-sig')

    unique_voyages_count = analysis_df['Voyage_ID'].nunique()
    print(f"\n[{window}일 윈도우] {unique_voyages_count}개 항차 상세 분석 완료")
    print(f" >> 모든 항차의 상세 분석 데이터를 '{ship_output_path}' 파일 하나로 저장했습니다.")

    # 항차별 오차 변화 예시 출력
    print(f"\n[{window}일 윈도우] 항차별 오차 변화 예시 (상위 5개 항차):")
    voyage_ids_to_show = analysis_df['Voyage_ID'].unique()[:5]
    if len(voyage_ids_to_show) > 0:
        for voyage_id in voyage_ids_to_show:
            print(f"\n--- 항차 ID: {voyage_id} ---")
            voyage_data = analysis_df[analysis_df['Voyage_ID'] == voyage_id][result_cols]
            print(voyage_data.to_string(index=False))
    else:
        print("분석할 항차 데이터가 없습니다.")

print(f"\n{'='*55}\n모든 분석 및 파일 저장이 완료되었습니다.")
