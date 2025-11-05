import pandas as pd
import glob
import os

# --- 설정 ---
# 입력 데이터가 있는 기본 폴더
base_input_folder = 'scenario_fixed_target' 
# 결과를 저장할 기본 폴더
output_folder = 'scenario_fixed_target_processed' 
# ---

# 입력 폴더 내의 모든 csv 파일을 재귀적으로 찾습니다.
file_pattern = os.path.join(base_input_folder, '**/*.csv')
csv_files = glob.glob(file_pattern, recursive=True)

print(f"총 {len(csv_files)}개의 파일을 '{base_input_folder}' 폴더에서 찾았습니다.")

# 결과 저장 폴더가 없으면 생성
os.makedirs(output_folder, exist_ok=True)
print(f"결과를 '{output_folder}' 폴더에 저장합니다.\n")


# 찾은 각 파일을 순회하며 처리합니다.
for file_path in csv_files:
    try:
        # 1. CSV 파일 읽기
        df = pd.read_csv(file_path)

        # 2. 필요한 컬럼만 선택
        columns_to_keep = ['Ship', '선사', '호출일', '모선항차', '선사항차', '접안예정일시','ETD', '출항예정일시']
        # 파일에 해당 컬럼이 없는 경우를 대비하여, 있는 컬럼만 선택
        df_processed = df[[col for col in columns_to_keep if col in df.columns]].copy()

        # 3. ETD와 출항예정일시를 datetime 형식으로 변환
        df_processed['ETD'] = pd.to_datetime(df_processed['ETD'], errors='coerce')
        df_processed['출항예정일시'] = pd.to_datetime(df_processed['출항예정일시'], errors='coerce')

        # 4. '시간차이(시)' 컬럼 추가 (절대 시간 차이)
        time_difference = (df_processed['ETD'] - df_processed['출항예정일시']).abs()
        df_processed['시간차이(시)'] = time_difference.dt.total_seconds() / 3600

        # 5. 결과 파일 저장 경로 설정
        # 입력 폴더 기준의 상대 경로를 만들어 출력 폴더에 동일한 구조로 저장
        relative_path = os.path.relpath(file_path, base_input_folder)
        output_path = os.path.join(output_folder, relative_path)
        
        # 저장할 하위 폴더 생성
        output_subfolder = os.path.dirname(output_path)
        os.makedirs(output_subfolder, exist_ok=True)
        
        # 6. CSV 파일로 저장
        df_processed.to_csv(output_path, index=False, encoding='utf-8-sig')

        print(f"성공: '{file_path}' -> '{output_path}'")

    except Exception as e:
        print(f"오류: '{file_path}' 처리 중 문제 발생 - {e}")

print("\n모든 파일 처리가 완료되었습니다.")