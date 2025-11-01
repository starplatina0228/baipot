import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import re
import pandas as pd
import pickle
import gurobipy as gp
from gurobipy import GRB

##### 크롤링 함수 #####
class PortScheduleCrawler:
    def __init__(self):
        self.base_url = "https://www.hpnt.co.kr/infoservice/vessel/vslScheduleList.jsp"
        self.session = requests.Session()
        
        #헤더 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
        })
    
    def get_schedule_data(self, start_date, end_date, output_format='json'):
        """
        원하는 날짜 범위의 선석 배정 현황을 크롤링
        
        Args:
            start_date (str): 시작날짜 (YYYY-MM-DD)
            end_date (str): 종료날짜 (YYYY-MM-DD) 
            output_format (str): 출력 형식 ('json', 'csv')
        """
        try:
            print(f"{start_date} ~ {end_date}")
            initial_response = self.session.get(self.base_url)
            print(f"session: {initial_response.status_code}")
            
            if initial_response.status_code != 200:
                print(f"session: {initial_response.status_code}")
                return None
        
            # 현재 설정된 날짜 범위 확인
            current_dates = self._get_current_date_range(initial_response.text)
            
            # 2단계: 날짜가 다르면 새로 검색, 같으면 현재 데이터 사용
            if current_dates['start'] == start_date and current_dates['end'] == end_date:
                result = self.parse_schedule_data(initial_response.text, output_format, start_date, end_date)
            else:
                result = self._search_with_date_range(initial_response.text, start_date, end_date, output_format)
            
            return result
                
        except Exception as e:
            print(f"{str(e)}")
            import traceback
            print(f"{traceback.format_exc()}")
            return None
    
    def _get_current_date_range(self, html_content):
        """현재 페이지에 설정된 날짜 범위 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        start_input = soup.find('input', {'name': 'strdStDate'})
        end_input = soup.find('input', {'name': 'strdEdDate'})
        
        return {
            'start': start_input.get('value', '') if start_input else '',
            'end': end_input.get('value', '') if end_input else ''
        }
    
    def _search_with_date_range(self, html_content, start_date, end_date, output_format):
        """새로운 날짜 범위로 검색 실행"""
        try:           
            soup = BeautifulSoup(html_content, 'html.parser')
            
            submit_form = soup.find('form', {'name': 'submitForm'})
            if not submit_form:
                print("No submitForm")
                return None
            
            # CSRF 토큰 추출
            csrf_token = self._extract_csrf_token_from_page(soup)
            
            if not csrf_token:
                print("토큰 없음")
            
            # 검색 폼 데이터 구성
            form_data = self._build_form_data(submit_form, start_date, end_date, csrf_token)
            
            # 검색 요청 실행
            response = self._submit_search_form(form_data)
            
            if response and response.status_code == 200:
                return self.parse_schedule_data(response.text, output_format, start_date, end_date)
            else:
                if response:
                    print(f"{response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"{str(e)}")
            return None
    
    def _extract_csrf_token_from_page(self, soup):
            """전체 페이지에서 CSRF 토큰 찾기 (JS 코드 내에서)"""
            page_text = str(soup)
            
            # name: 'CSRF_TOKEN', value:'...' 구조
            # re.DOTALL 플래그는 줄바꿈(...)이 있어도 찾을 수 있음
            # name\s*:\s*['\"]CSRF_TOKEN['\"] name 이라는 글자뒤 : 이 나오고 "CSRF_TOKEN" 찾음
            # \s*은 공백이 0개 이상, 공백 처리 e.g. name: , name :
            # .*? 는 value 까지의 모든 문자 (최소 매칭) .* : 어떤 문자든, ? : 짧게
            # ['\"]([^'\"]+)['\"] value 뒤에 ' 또는 " 로 감싸진 값 추출, ([^'\"]+) 토큰값 (따옴표가 아닌 문자)
            pattern = r"name\s*:\s*['\"]CSRF_TOKEN['\"].*?value\s*:\s*['\"]([^'\"]+)['\"]"
            
            match = re.search(pattern, page_text, re.DOTALL)
            
            if match:
                token = match.group(1)
                # print(f"name: 'CSRF_TOKEN', value:'...' 구조 : {token}")
                return token

            print("No CSRF")
            return ''
    
    def _build_form_data(self, form, start_date, end_date, csrf_token):
        """검색 폼 데이터 구성"""
        # 기본 검색 데이터
        form_data = {
            'strdStDate': start_date,       # 시작날짜
            'strdEdDate': end_date,         # 종료날짜
            'route': '',                    # 선명(ROUTE) - 빈값이면 전체
            'isSearch': 'Y',                # 검색 플래그
            'page': '1',                    # 페이지 번호
            'URI': '',                      # URI
            'userID': '',                   # 사용자 ID
            'groupID': 'U999',              # 그룹 ID
            'tmnCod': 'H'                   # 터미널 코드
        }
        
        # CSRF 토큰 추가
        if csrf_token:
            form_data['CSRF_TOKEN'] = csrf_token
        
        return form_data
    
    def _submit_search_form(self, form_data):
        """검색 폼 제출"""
        try:
            # 요청 헤더 설정
            headers = {
                'Referer': self.base_url,
                'Origin': 'https://www.hpnt.co.kr',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            # POST
            response = self.session.post(self.base_url, data=form_data, headers=headers)
            
            print(f"post: {response.status_code}")
            
            if response.status_code == 200:
                return response
            else:
                print(f"HTTP error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"{str(e)}")
            return None
    
    def parse_schedule_data(self, html_content, output_format, start_date, end_date):
        """HTML에서 선박 스케줄 데이터 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 선박 스케줄 테이블 찾기
        target_table = self._find_schedule_table(soup)
        
        if not target_table:
            raise ValueError("No schedule table found")
        
        # 테이블에서 선박 데이터 추출
        schedule_data = self._extract_vessel_data(target_table)
        
        if not schedule_data:
            raise ValueError("No vessel data extracted")
        
        print(f"total {len(schedule_data)} vessel data extracted")
        
        # 결과 데이터 구성
        if output_format == 'json':
            return {
                'success': True,
                'data_count': len(schedule_data),
                'period': f"{start_date} ~ {end_date}",
                'schedule_data': schedule_data,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            return schedule_data
    
    def _find_schedule_table(self, soup):
        """선박 스케줄 테이블 찾기"""
        # tblType_08 클래스의 테이블
        table_div = soup.find('div', class_='tblType_08')
        if table_div:
            table = table_div.find('table')
            if table:
                return table

        return None
    
    def _extract_vessel_data(self, table):
        """테이블에서 선박 데이터 추출"""
        schedule_data = []
        
        # tbody가 있으면 tbody에서, 없으면 table에서 직접 tr 추출
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')
                
        # 헤더 행 제외하고 데이터 행만 추출
        data_rows = []
        for row in rows:
            if row.find('th'):  # 헤더 행은 제외
                continue
            if row.find('td'):  # 데이터가 있는 행만 포함
                data_rows.append(row)
        
        # 각 데이터 행 처리
        for i, row in enumerate(data_rows):
            cells = row.find_all('td')
            
            try:
                # 선박 데이터 추출
                vessel_data = self._parse_vessel_row(cells)
                
                # ARRIVE, PLANNED 상태이면서 선명 있는 데이터만 포함
                if vessel_data and vessel_data.get('선명', '').strip():
                    # if vessel_data.get('상태') in ['ARRIVED', 'PLANNED']:
                    if vessel_data.get('상태') in ["DEPARTED"]: #시나리오 테스트용, DEPATED만 고려하여 ETD 서비스 호출 시점에 따른 결과값 비교 위함
                        schedule_data.append(vessel_data)
                    
            except Exception as e:
                print(f"{i+1} row, error: {str(e)}")
                continue
        
        return schedule_data
    
    def _parse_vessel_row(self, cells):
        """선박 정보 행 파싱"""
        vessel_data = {
            '선석': self.clean_text(cells[0].text),
            '선사': self.clean_text(cells[1].text),
            '모선항차': self.clean_text(cells[2].text),
            '선사항차': self.clean_text(cells[3].text),
            '선명': self.clean_text(cells[4].text),
            '항로': self.clean_text(cells[5].text),
            '반입마감시한': self.clean_text(cells[6].text),
            '접안예정일시': self.clean_text(cells[7].text),
            '출항예정일시': self.clean_text(cells[8].text),
            '양하': self.clean_text(cells[9].text),
            '적하': self.clean_text(cells[10].text),
            'Shift': self.clean_text(cells[11].text),
            'AMP': self.clean_text(cells[12].text),
            '상태': self.clean_text(cells[13].text)
            }

        return vessel_data
    
    def clean_text(self, text):
        """텍스트 정리"""
        if text:
            return re.sub(r'\s+', ' ', text.strip())
        return ''
    
    def save_to_file(self, data, filename, file_format='json'):
        """파일로 저장"""
        try:
            if file_format == 'json':
                with open(f"{filename}.json", 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
            elif file_format == 'csv':
                import csv
                schedule_data = data['schedule_data'] if isinstance(data, dict) else data
                
                if schedule_data:
                    with open(f"{filename}.csv", 'w', newline='', encoding='utf-8-sig') as f:
                        writer = csv.DictWriter(f, fieldnames=schedule_data[0].keys())
                        writer.writeheader()
                        writer.writerows(schedule_data)
                
        except Exception as e:
            print(f"{str(e)}")

def get_work_plan_data(start_date, end_date, output_format='list'):
    """
    지정된 기간의 선석 계획 데이터를 크롤링하여 DataFrame 또는 JSON으로 반환합니다.

    - output_format='list' (기본값): 크롤링된 데이터를 pandas DataFrame으로 반환합니다.
    - output_format='json': 크롤링된 데이터를 JSON 객체(dict)로 반환합니다.

    데이터 흐름:
    1. PortScheduleCrawler 객체를 생성합니다.
    2. crawler.get_schedule_data()를 호출하여 HPNT 웹사이트에서 선박 스케줄을 크롤링합니다.
    3. output_format에 따라 DataFrame 또는 JSON으로 가공하여 반환합니다.

    Args:
        start_date (str): 시작일 (YYYY-MM-DD)
        end_date (str): 종료일 (YYYY-MM-DD)
        output_format (str): 반환 형식 ('list' 또는 'json'). 기본값은 'list'입니다.

    Returns:
        pandas.DataFrame or dict: 크롤링된 데이터.
                                  'list' 형식일 경우 DataFrame,
                                  'json' 형식일 경우 dict.
                                  실패 시 예외를 발생시킵니다.
    """
    crawler = PortScheduleCrawler()

    if output_format == 'json':
        # JSON 형식 요청 시, crawler는 dict를 반환
        result_data = crawler.get_schedule_data(start_date, end_date, output_format='json')
        if not result_data:
            raise ValueError("No data crawled")
        return result_data
    
    # 'list' 형식 요청 시, crawler는 list를 반환
    result_data = crawler.get_schedule_data(start_date, end_date, output_format='list')
    if result_data:
        df = pd.DataFrame(result_data)
        df.drop_duplicates(subset=['선명', '모선항차'], inplace=True)
        return df
    else:
        raise ValueError("No data crawled or data is empty")

##### 선박 작업시간 예측 관련 함수 #####

def preprocess_for_prediction(df):
    """
    LGBM 모델 예측을 위해 데이터를 전처리합니다.
    """
    ship_info_df = pd.read_csv('ship_info.csv')
    ship_info_df['merge_key'] = ship_info_df['선사'].astype(str) + '_' + ship_info_df['선명'].str.replace(r'\s+', '', regex=True)
    ship_info_df.drop_duplicates(subset=['merge_key'], inplace=True)
    df['merge_key'] = df['선사'].astype(str) + '_' + df['선명'].str.replace(r'\s+', '', regex=True)
    
    # merge_key와 모선항차를 기반으로 병합
    df = pd.merge(df, ship_info_df[['merge_key', '총톤수', 'LOA']], on='merge_key', how='left')
    df.drop(columns=['merge_key'], inplace=True)

    # 총톤수 또는 LOA 정보가 없는 경우, 해당 선박 정보 출력 및 평균값으로 대체
    missing_info_rows = df[df['총톤수'].isnull() | df['LOA'].isnull()]
    if not missing_info_rows.empty:
        print("일부 선박의 '총톤수' 또는 'LOA' 정보가 없어 평균값으로 대체:")
        for index, row in missing_info_rows.iterrows():
            print(f"- 선사: {row['선사']}, 선명: {row['선명']}")
        
        # 평균값으로 결측치 대체
        df['총톤수'].fillna(df['총톤수'].mean(), inplace=True)
        df['LOA'].fillna(df['LOA'].mean(), inplace=True)

    df = df.rename(columns={'Shift': 'shift'})
    df['접안예정일시'] = pd.to_datetime(df['접안예정일시'], errors='coerce')
    df['양하'] = pd.to_numeric(df['양하'], errors='coerce').fillna(0)
    df['적하'] = pd.to_numeric(df['적하'], errors='coerce').fillna(0)
    df['양적하물량'] = df['양하'] + df['적하']

    dt_series = df['접안예정일시']
    df['입항시간'] = dt_series.dt.hour
    df['입항요일'] = dt_series.dt.dayofweek
    df['입항분기'] = dt_series.dt.quarter
    df['입항계절'] = dt_series.dt.month.map({
        1:'겨울', 2:'겨울', 3:'봄', 4:'봄', 5:'봄', 6:'여름',
        7:'여름', 8:'여름', 9:'가을', 10:'가을', 11:'가을', 12:'겨울'
    })

    # Feature-specific type conversion for the new model
    numeric_cols = ['shift', '양적하물량', '총톤수', 'LOA', '입항시간', '입항분기']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    categorical_cols = ['입항요일', '입항계절']
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')
            
    return df

def predict_work_time(crawled_df):
    """
    크롤링된 데이터프레임을 받아 전처리 후, 작업소요시간을 예측하여 반환

    데이터 흐름:
    1. `preprocess_for_prediction(crawled_df)`를 호출하여 LGBM 모델에 필요한 형태로 데이터를 가공
       - `hpnt_tonnage_loa.csv` 파일에서 선박의 '총톤수'와 'LOA' 정보를 가져와 병합
       - 날짜/시간 관련 피처(입항시간, 요일, 분기, 계절)를 생성
       - '양적하물량' 등 모델에 사용될 피처를 계산
    2. 전처리된 데이터프레임(`processed_df`) 생성
    3. `lgbm_model.pkl` 파일을 로드하여 예측 모델을 준비
    4. `processed_df`에서 모델이 학습한 피처들을 선택하여 예측을 수행
    5. 예측 결과를 `processed_df`에 'predicted_work_time'이라는 새로운 컬럼으로 추가하여 반환

    Args:
        crawled_df (pd.DataFrame): `crawl_hpnt.get_work_plan_data()`를 통해 얻은, 크롤링된 원본 데이터프레임.

    Returns:
        pd.DataFrame: 원본 데이터에 'predicted_work_time' 컬럼이 추가된 데이터프레임.
    """
    processed_df = preprocess_for_prediction(crawled_df)

    with open('lgbm_weight.pkl', 'rb') as f:
        lgbm_model = pickle.load(f)

    # Features for the new model (without '선사')
    features = ['입항시간', '입항요일', '입항분기', '입항계절', '총톤수', '양적하물량', 'shift']
    
    if not all(f in processed_df.columns for f in features):
        missing_features = [f for f in features if f not in processed_df.columns]
        raise ValueError(f"missing values :  {missing_features}")

    X_predict = processed_df[features]
        
    predicted_time = lgbm_model.predict(X_predict)
    processed_df['predicted_work_time'] = predicted_time

    return processed_df


##### MILP 최적화 관련 함수 #####

def run_milp_model(processed_df):
    """
    Gurobi MILP 모델을 실행, 최적의 선석 배정 계획을 도출

    1. `processed_df`에서 MILP 모델에 필요한 입력 데이터를 추출
       - 작업 소요 시간 (s_i): `predicted_work_time` 컬럼 (분으로 변환)
       - 선박 도착 시간 (a_i): `접안예정일시` 컬럼 (가장 이른 시간을 기준으로 시간 단위로 변환)
       - 선박 길이 (l_i): `LOA` 컬럼
    2. Gurobi 모델을 생성하고, 결정 변수 정의
    3. 목적 함수(총 대기 시간 최소화)와 제약 조건을 설정합니다.
    4. Gurobi 옵티마이저를 실행
    5. 최적해가 발견되면, 결과를 pandas DataFrame으로 정리
       - DataFrame에는 각 선박의 최적 시작 시간, 종료 시간, 대기 시간, 선석 위치 등의 정보가 포함

    Args:
        processed_df (pd.DataFrame): `lgbm.predict_work_time()`을 거친 데이터프레임.
                                     'predicted_work_time', '접안예정일시', 'LOA', '선명' 컬럼을 포함해야 함

    Returns:
        pd.DataFrame: 최적화된 선석 배정 결과. 각 선박의 ID, 시작/종료 시간, 위치 등 상세 정보 포함.
                      최적해를 찾지 못하면 None을 반환.
    """

    # --- 1. 입력 데이터 추출 및 변환 ---
    # 작업소요시간 (predicted_work_time은 분 단위로 가정)
    s_i = processed_df['predicted_work_time'].tolist()

    # 입항시간 (가장 이른 시간을 기준으로 분 단위로 변환)
    start_time_ref = processed_df['접안예정일시'].min()
    a_i_minutes = ((processed_df['접안예정일시'] - start_time_ref).dt.total_seconds() / 60).tolist()
    
    # 결과 저장용 시간 단위 입항 시간
    a_i = [m / 60 for m in a_i_minutes]

    # 선박길이 (LOA)
    l_i = processed_df['LOA'].tolist()
    N = len(processed_df)

    L = 1150  # 부두길이 (m)

    # 선석 간격 시간 (분)
    buffer_minutes = 60

    # --- 2. Gurobi 모델 생성 ---
    model = gp.Model("BAIPOT")

    # --- 3. 결정 변수 ---
    t = model.addVars(N, vtype=GRB.CONTINUOUS, lb=0, name="start_time")
    p = model.addVars(N, vtype=GRB.CONTINUOUS, lb=0, ub=L, name="position")
    w = model.addVars(N, vtype=GRB.CONTINUOUS, lb=0, name="waiting_time")
    x = model.addVars(N, N, vtype=GRB.BINARY, name="left_of")
    y = model.addVars(N, N, vtype=GRB.BINARY, name="before")

    # --- 4. 목적 함수 ---
    model.setObjective(gp.quicksum(w[i] for i in range(N)), GRB.MINIMIZE)

    # --- 5. 제약 조건 ---
    model.addConstrs((w[i] == t[i] - a_i_minutes[i] for i in range(N)), name="waiting_time")
    model.addConstrs((t[i] >= a_i_minutes[i] for i in range(N)), name="arrival_constraints")
    model.addConstrs((p[i] + l_i[i] <= L for i in range(N)), name="berth_length_constraints")

    M_time = sum(s_i) + max(a_i_minutes) if a_i_minutes else sum(s_i)
    M_space = 2 * L

    for i in range(N):
        for j in range(N):
            if i != j:
                model.addConstr(p[i] + l_i[i] <= p[j] + M_space * (1 - x[i,j]), name=f"spatial_left_{i}_{j}")
                model.addConstr(p[j] + l_i[j] <= p[i] + M_space * (1 - x[j,i]), name=f"spatial_right_{i}_{j}")
                model.addConstr(t[i] + s_i[i] + buffer_minutes <= t[j] + M_time * (1 - y[i,j]), name=f"temporal_before_{i}_{j}")
                model.addConstr(t[j] + s_i[j] + buffer_minutes <= t[i] + M_time * (1 - y[j,i]), name=f"temporal_after_{i}_{j}")

    model.addConstrs((x[i,j] + x[j,i] + y[i,j] + y[j,i] >= 1 for i in range(N) for j in range(i + 1, N)), name="separation_required")

    # --- 6. 모델 최적화 ---
    model.optimize()

    # --- 7. 결과 처리 및 시각화 ---
    if model.status == GRB.OPTIMAL:
        solution = []
        for i in range(N):
            start_minutes = t[i].x
            start_hours = start_minutes / 60
            waiting_minutes = w[i].x
            waiting_hours = waiting_minutes / 60
            completion_minutes = start_minutes + s_i[i]
            completion_hours = completion_minutes / 60
            position_m = p[i].x

            solution.append({
                'Ship': processed_df.iloc[i]['선명'],
                '모선항차': processed_df.iloc[i]['모선항차'],
                'Ship_ID': i + 1,
                'Arrival_h': a_i[i],
                'Start_h': start_hours,
                'Completion_h': completion_hours,
                'Waiting_h': waiting_hours,
                'Service_min': s_i[i],
                'Service_h': s_i[i] / 60,
                'Length_m': l_i[i],
                'Position_m': position_m,
                'End_Position_m': position_m + l_i[i]
            })

        df_solution = pd.DataFrame(solution)
        df_solution = df_solution.sort_values('Ship_ID').reset_index(drop=True)

        print(df_solution[['Ship', 'Start_h', 'Completion_h', 'Waiting_h', 'Position_m']].round(2))
        
        return df_solution

    elif model.status == GRB.INFEASIBLE:
        model.computeIIS()
        for c in model.getConstrs():
            if c.IISConstr:
                print(f"  Infeasible constraint: {c.constrName}")
        return None
    else:
        return None