import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import time
import re
from urllib.parse import urljoin

class PortScheduleCrawler:
    def __init__(self):
        self.base_url = "https://www.hpnt.co.kr/infoservice/vessel/vslScheduleList.jsp"
        self.session = requests.Session()
        
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
        Args:
            start_date (str): 시작날짜 (YYYY-MM-DD)
            end_date (str): 종료날짜 (YYYY-MM-DD) 
            output_format (str): 출력 형식 ('json', 'csv')
        """
        try:
            print(f"{start_date} ~ {end_date}")
            print("=" * 50)
            
            initial_response = self.session.get(self.base_url)
            print(f"response : {initial_response.status_code}")
            
            if initial_response.status_code != 200:
                print(f"page load failure : {initial_response.status_code}")
                return None
            
            # 현재 설정된 날짜 범위 확인
            current_dates = self._get_current_date_range(initial_response.text)
            print(f"현재 페이지 날짜: {current_dates['start']} ~ {current_dates['end']}")
            print(f"요청 날짜: {start_date} ~ {end_date}")
            
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
            
            # submitForm 찾기
            submit_form = soup.find('form', {'name': 'submitForm'})
            if not submit_form:
                print("submitForm을 찾을 수 없습니다.")
                return None
            
            # CSRF 토큰 추출
            csrf_token = self._extract_csrf_token(submit_form)
            
            # 토큰이 없으면 전체 페이지에서 다시 찾기
            if not csrf_token:
                print("submitForm에서 토큰을 찾지 못함 - 전체 페이지에서 재검색")
                csrf_token = self._extract_csrf_token_from_page(soup)
            
            print(f"CSRF 토큰: {csrf_token if csrf_token else '토큰 없음'}")
            
            # 검색 폼 데이터 구성
            form_data = self._build_form_data(submit_form, start_date, end_date, csrf_token)
            
            # 검색 요청 실행
            response = self._submit_search_form(form_data)
            
            if response and response.status_code == 200:
                print("검색 완료 - 결과 데이터 파싱")
                return self.parse_schedule_data(response.text, output_format, start_date, end_date)
            else:
                print("검색 실패")
                if response:
                    print(f"응답 내용 미리보기: {response.text[:200]}...")
                return None
                
        except Exception as e:
            print(f"검색 중 오류: {str(e)}")
            return None
    
    def _extract_csrf_token(self, form):
        """CSRF 토큰 추출 (여러 방법 시도)"""
        # 방법 1: submitForm 내에서 CSRF_TOKEN input 찾기
        csrf_input = form.find('input', {'name': 'CSRF_TOKEN'})
        if csrf_input and csrf_input.get('value'):
            token = csrf_input.get('value')
            print(f"submitForm에서 토큰 추출 = {token}")
            return token
        
        # 방법 2: 전체 페이지에서 CSRF_TOKEN 찾기 (submitForm 밖에 있을 수 있음)
        soup = form.find_parent('html') or form.find_parent() 
        if soup:
            all_csrf_inputs = soup.find_all('input', {'name': 'CSRF_TOKEN'})
            for csrf_input in all_csrf_inputs:
                token = csrf_input.get('value', '')
                if token.strip():
                    print(f"전체 페이지에서 토큰 추출 = {token}")
                    return token
        
        # 방법 3: JavaScript에서 동적으로 설정된 토큰 찾기
        if hasattr(form, 'parent') and form.parent:
            page_text = str(form.parent)
            import re
            js_token_match = re.search(r"CSRF_TOKEN['\"]?\s*[,:]\s*['\"]([^'\"]+)['\"]", page_text)
            if js_token_match:
                token = js_token_match.group(1)
                print(f"JavaScript에서 토큰 추출 = {token}")
                return token
        
        print("CSRF 토큰 추출 실패")
        return ''
    
    def _extract_csrf_token_from_page(self, soup):
        """전체 페이지에서 CSRF 토큰 찾기"""
        # 모든 CSRF_TOKEN input 태그 찾기
        csrf_inputs = soup.find_all('input', {'name': 'CSRF_TOKEN'})
        
        print(f"페이지에서 발견된 CSRF_TOKEN input 개수: {len(csrf_inputs)}")
        
        for i, csrf_input in enumerate(csrf_inputs):
            token = csrf_input.get('value', '').strip()
            form_name = 'Unknown'
            parent_form = csrf_input.find_parent('form')
            if parent_form:
                form_name = parent_form.get('name', 'Unnamed')
            
            print(f"토큰 {i+1}: '{token}' (폼: {form_name})")
            
            if token:  # 첫 번째 유효한 토큰 반환
                return token
        
        # JavaScript에서 동적 설정 확인
        page_text = str(soup)
        import re
        
        # 패턴 1: CSRF_TOKEN: 'value' 또는 CSRF_TOKEN': 'value'
        js_patterns = [
            r"CSRF_TOKEN['\"]?\s*:\s*['\"]([^'\"]{30,})['\"]",
            r"CSRF_TOKEN['\"]?\s*,\s*value\s*:\s*['\"]([^'\"]{30,})['\"]",
            r"name:\s*['\"]CSRF_TOKEN['\"].*?value:\s*['\"]([^'\"]{30,})['\"]"
        ]
        
        for pattern in js_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                token = match.group(1)
                print(f"JavaScript 패턴에서 토큰 발견: {token}")
                return token
        
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
        
        # 폼에서 추가 hidden 필드들 찾아서 추가
        hidden_inputs = form.find_all('input', type='hidden')
        print(f"숨겨진 필드 {len(hidden_inputs)}개 발견")
        
        for hidden in hidden_inputs:
            name = hidden.get('name')
            value = hidden.get('value', '')
            if name and name not in form_data:  # 중복 방지
                form_data[name] = value
                print(f"      ➕ {name} = {value}")
        
        print(f"최종 폼 데이터: {len(form_data)}개 필드")
        for key, value in form_data.items():
            if len(str(value)) > 50:  # 긴 값은 줄여서 표시
                print(f"      📝 {key} = {str(value)[:50]}...")
            else:
                print(f"      📝 {key} = {value}")
        
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
            
            # POST 요청으로 검색 실행
            response = self.session.post(self.base_url, data=form_data, headers=headers)
            
            print(f"응답 상태: {response.status_code}")
            
            if response.status_code == 200:

                return response
            else:
                print(f"HTTP 오류: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"요청 실행 오류: {str(e)}")
            return None
    
    def parse_schedule_data(self, html_content, output_format, start_date, end_date):
        """HTML에서 선박 스케줄 데이터 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        print("데이터 파싱 중...")
        
        # 선박 스케줄 테이블 찾기
        target_table = self._find_schedule_table(soup)
        
        if not target_table:
            print("스케줄 테이블을 찾을 수 없습니다.")
            return None
        
        print("스케줄 테이블 발견!")
        
        # 테이블에서 선박 데이터 추출
        schedule_data = self._extract_vessel_data(target_table)
        
        if not schedule_data:
            print("파싱된 선박 데이터가 없습니다.")
            return None
        
        print(f"{len(schedule_data)}건의 선박 데이터 파싱")
        
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
        # 방법 1: tblType_08 클래스의 테이블
        table_div = soup.find('div', class_='tblType_08')
        if table_div:
            table = table_div.find('table')
            if table:
                print("tblType_08 클래스로 테이블 찾음")
                return table
        
        # 방법 2: caption이 "선석 배정현황(목록)"인 테이블
        captions = soup.find_all('caption')
        for caption in captions:
            if '선석' in caption.text and '배정' in caption.text:
                table = caption.find_parent('table')
                if table:
                    print("caption으로 테이블 찾음")
                    return table
        
        # 방법 3: 가장 많은 행을 가진 테이블 (데이터 테이블일 가능성이 높음)
        tables = soup.find_all('table')
        max_rows = 0
        best_table = None
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) > max_rows and len(rows) > 5:  # 최소 5행 이상
                # 테이블 내용에 선박 관련 키워드가 있는지 확인
                table_text = table.get_text()
                keywords = ['선명', '선사', '선석', '접안', '출항']
                keyword_count = sum(1 for keyword in keywords if keyword in table_text)
                
                if keyword_count >= 3:  # 3개 이상 키워드가 있으면 선박 테이블로 판단
                    max_rows = len(rows)
                    best_table = table
        
        if best_table:
            print(f"최대 행수({max_rows})와 키워드로 테이블 찾음")
            return best_table
        
        return None
    
    def _extract_vessel_data(self, table):
        """테이블에서 선박 데이터 추출"""
        schedule_data = []
        
        # tbody가 있으면 tbody에서, 없으면 table에서 직접 tr 추출
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')
        
        print(f"총 {len(rows)}개 행")
        
        # 헤더 행 제외하고 데이터 행만 추출
        data_rows = []
        for row in rows:
            if row.find('th'):  # 헤더 행은 제외
                continue
            if row.find('td'):  # 데이터가 있는 행만 포함
                data_rows.append(row)
        
        print(f"행 {len(data_rows)}개 처리")
        
        # 각 데이터 행 처리
        for i, row in enumerate(data_rows):
            cells = row.find_all('td')
            
            # 최소 10개 이상의 셀이 있어야 유효한 선박 데이터로 판단
            if len(cells) < 10:
                continue
            
            try:
                # 선박 데이터 추출
                vessel_data = self._parse_vessel_row(row, cells)
                
                # 유효한 데이터인지 확인 (선명이 있어야 함)
                if vessel_data and vessel_data.get('선명', '').strip():
                    schedule_data.append(vessel_data)
                    
                    # 진행상황 출력 (10건마다)
                    if len(schedule_data) % 10 == 0:
                        print(f"{len(schedule_data)}건 처리 완료...")
                
            except Exception as e:
                print(f"{i+1} 처리 중 오류: {str(e)}")
                continue
        
        return schedule_data
    
    def _parse_vessel_row(self, row, cells):
        """선박 정보 행 파싱"""
        # row class에서 상태 정보 추출
        row_class = row.get('class', [])
        status = self._get_vessel_status(row_class)
        
        # 셀 개수에 따라 유연하게 매핑
        if len(cells) >= 14:
            # 표준 14개 컬럼 구조
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
                '상태': self.clean_text(cells[13].text) or status,
            }
        else:
            # 컬럼이 적을 경우 기본 필드만 매핑
            field_names = ['선석', '선사', '모선항차', '선사항차', '선명', '항로', '접안예정일시', '출항예정일시', '상태']
            vessel_data = {}
            
            for i, field in enumerate(field_names):
                if i < len(cells):
                    vessel_data[field] = self.clean_text(cells[i].text)
                else:
                    vessel_data[field] = ''
            
            if not vessel_data.get('상태'):
                vessel_data['상태'] = status
        
        # 메타 정보는 제외하고 선박 데이터만 반환
        return vessel_data
    
    def _get_vessel_status(self, row_class):
        """row class에서 선박 상태 추출"""
        if 'color_departed' in row_class:
            return 'DEPARTED'   # 출항완료
        elif 'color_arrived' in row_class:
            return 'ARRIVED'    # 접안완료
        elif 'color_planned' in row_class:
            return 'PLANNED'    # 예정
        else:
            return ''
    
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
                print(f"JSON 저장: {filename}.json")
                
            elif file_format == 'csv':
                import csv
                schedule_data = data['schedule_data'] if isinstance(data, dict) else data
                
                if schedule_data:
                    with open(f"{filename}.csv", 'w', newline='', encoding='utf-8-sig') as f:
                        writer = csv.DictWriter(f, fieldnames=schedule_data[0].keys())
                        writer.writeheader()
                        writer.writerows(schedule_data)
                    print(f"CSV 저장: {filename}.csv")
                
        except Exception as e:
            print(f"파일 저장 오류: {str(e)}")
    
    def get_summary(self, data):
        """데이터 요약 정보"""
        schedule_data = data['schedule_data'] if isinstance(data, dict) else data
        
        if not schedule_data:
            return None
        
        # 각종 통계
        berth_count = {}    # 선석별
        status_count = {}   # 상태별  
        shipping_count = {} # 선사별
        
        for vessel in schedule_data:
            # 선석별 집계
            berth = vessel.get('선석', 'Unknown')
            berth_count[berth] = berth_count.get(berth, 0) + 1
            
            # 상태별 집계
            status = vessel.get('상태', 'Unknown')
            status_count[status] = status_count.get(status, 0) + 1
            
            # 선사별 집계
            shipping = vessel.get('선사', 'Unknown')
            shipping_count[shipping] = shipping_count.get(shipping, 0) + 1
        
        return {
            '전체_선박수': len(schedule_data),
            '선석별_현황': berth_count,
            '상태별_현황': status_count,
            '선사별_현황': shipping_count
        }

def main():
    crawler = PortScheduleCrawler()
    
    start_date = "2025-07-22"
    end_date = "2025-08-25"  
    
    print(f"조회 기간: {start_date} ~ {end_date}")
    
    # 크롤링 실행
    result = crawler.get_schedule_data(start_date, end_date, output_format='json')
    
    if result:
        print(f"수집된 선박 수: {result['data_count']}척")
        
        # 파일 저장
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"hpnt_schedule_{start_date}_to_{end_date}_{timestamp}"
        
        crawler.save_to_file(result, filename, 'json')
        crawler.save_to_file(result, filename, 'csv')
        
        # 샘플 데이터 출력
        for i, vessel in enumerate(result['schedule_data'][:5]):
            print(f"{i+1}. {vessel['선명']} ({vessel['선사']})")
            print(f"선석: {vessel['선석']} | 상태: {vessel['상태']}")
            print(f"접안예정일시: {vessel.get('접안예정일시', 'N/A')}")
            print(f"출항예정일시: {vessel.get('출항예정일시', 'N/A')}")
    else:
        print("\nfailure")

if __name__ == "__main__":
    print("HPNT")
    print("=" * 60)
    main()