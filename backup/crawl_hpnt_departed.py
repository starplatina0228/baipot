import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import time
import re
from urllib.parse import urljoin
import pandas as pd

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

            # 2. 'CSRF_TOKEN', value:'...' 구조
            # pattern_fallback = r"['\"]CSRF_TOKEN['\"].*?value\s*:\s*['\"]([^'\"]+)['\"]"
            # match_fallback = re.search(pattern_fallback, page_text, re.DOTALL)

            # if match_fallback:
            #     token = match_fallback.group(1)
            #     print(f"'CSRF_TOKEN', value:'...' 구조: {token}")
            #     return token

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
        
        ## 폼에서 추가 hidden 필드들 찾아서 추가
        # hidden_inputs = form.find_all('input', type='hidden')
        
        # for hidden in hidden_inputs:
        #     name = hidden.get('name')
        #     value = hidden.get('value', '')
        #     if name and name not in form_data:  # 중복 방지
        #         form_data[name] = value

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
        
        # # caption이 "선석 배정현황(목록)"인 테이블
        # captions = soup.find_all('caption')
        # for caption in captions:
        #     if '선석 배정현황(목록)' in caption.text:
        #         table = caption.find_parent('table')
        #         if table:
        #             return table
        
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
                    if vessel_data.get('상태') in ['DEPARTED']:
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
        # 여러 공백을 하나로, 앞뒤 공백 제거
        # 띄어쓰기 넣었는데 뺄수도 있음 ???
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
        return df
    else:
        raise ValueError("No data crawled or data is empty")

if __name__ == "__main__":
    today = datetime.now().strftime('%Y-%m-%d')
    end_day = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
    
    print("--- DataFrame (output_format='list') ---")
    try:
        # output_format='list'가 기본값이지만 명시적으로 호출
        df = get_work_plan_data(start_date=today, end_date=end_day, output_format='list')
        if df is not None:
            print(df.head())
    except ValueError as e:
        print(e)

    print("--- JSON (output_format='json') ---")
    try:
        json_data = get_work_plan_data(start_date=today, end_date=end_day, output_format='json')
        if json_data:
            with open("hpnt_schedule.json", 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
    except ValueError as e:
        print(e)