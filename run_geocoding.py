import pandas as pd
import re
import requests
import time
import sys
import urllib3

# SSL 인증서 
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [설정] 브이월드 API 키 ---
API_KEY = 'E683355C-75BE-303E-8C83-47DA0A3D2834'

def normalize_address(addr):
    """주소를 단일 지번 형식으로 정규화하는 함수"""
    if pd.isna(addr) or not isinstance(addr, str):
        return None
    
    # 1. 불필요한 문구 제거 (일원, 외 N필지 등)
    addr = re.sub(r'일원.*|외\s*\d*필지.*', '', addr)
    
    # 2. 복합 주소 중 첫 번째 주소만 선택
    addr = addr.split(',')[0].split('~')[0].strip()
    
    # 3. 띄어쓰기 교정 (예: 월연리401 -> 월연리 401)
    addr = re.sub(r'([가-힣])(\d)', r'\1 \2', addr)
    
    # 4. 공백 정리 및 접두어 확인
    addr = " ".join(addr.split())
    if "군산" not in addr:
        addr = f"전북특별자치도 군산시 {addr}"
    elif "전북" not in addr:
        addr = f"전북특별자치도 {addr}"
        
    return addr

def get_vworld_data(address):
    """지번 주소로 좌표를 구하고, 그 좌표로 도로명 주소를 가져오는 함수"""
    # 1단계: 지번 주소 -> 위경도 좌표 (Geocoding)
    coord_url = "https://api.vworld.kr/req/address"
    coord_params = {
        "service": "address",
        "request": "getcoord",
        "crs": "epsg:4326",
        "address": address,
        "format": "json",
        "type": "parcel",
        "key": API_KEY
    }
    
    lat, lon, road_addr = None, None, None
    
    try:
        res = requests.get(coord_url, params=coord_params, timeout=10, verify=False)
        if res.status_code == 200:
            data = res.json()
            if data['response']['status'] == 'OK':
                p = data['response']['result']['point']
                lat, lon = float(p['y']), float(p['x'])
                
                # 2단계: 좌표 -> 도로명 주소 (Reverse Geocoding)
                # 좌표를 찾은 경우에만 실행
                addr_url = "https://api.vworld.kr/req/address"
                addr_params = {
                    "service": "address",
                    "request": "getAddress",
                    "point": f"{lon},{lat}",
                    "type": "road", # 도로명 주소 요청
                    "format": "json",
                    "key": API_KEY
                }
                res_addr = requests.get(addr_url, params=addr_params, timeout=10, verify=False)
                if res_addr.status_code == 200:
                    addr_data = res_addr.json()
                    if addr_data['response']['status'] == 'OK':
                        road_addr = addr_data['response']['result'][0]['text']
    except Exception:
        pass
    
    return lat, lon, road_addr

def main():
    input_file = '군산시_자연재해_위험지역_현황.csv'
    output_file = '군산_위험지역_도로명_좌표_최종.csv'
    
    print(f"[{time.strftime('%H:%M:%S')}] 작업을 시작합니다.")
    
    # 1. 파일 로드
    try:
        df = pd.read_csv(input_file, encoding='utf-8-sig')
    except:
        df = pd.read_csv(input_file, encoding='cp949')
    
    # 2. 정규화
    df_geo = df.dropna(subset=['대표지번(위치)']).copy()
    df_geo['정규화_지번주소'] = df_geo['대표지번(위치)'].apply(normalize_address)
    
    # 3. 데이터 추출 (지번 -> 좌표 -> 도로명)
    total = len(df_geo)
    print(f"총 {total}건의 데이터 변환 중... (도로명 주소 추출 포함)")
    
    lats, lons, roads = [], [], []
    
    for i, addr in enumerate(df_geo['정규화_지번주소']):
        lat, lon, road = get_vworld_data(addr)
        lats.append(lat)
        lons.append(lon)
        roads.append(road)
        
        if (i + 1) % 5 == 0 or (i + 1) == total:
            sys.stdout.write(f"\r진행률: {(i + 1) / total * 100:.1f}% 완료 ({i + 1}/{total})")
            sys.stdout.flush()
        
        time.sleep(0.07) # API 두 번 호출하므로 지연 시간 조정
    
    df_geo['도로명_주소'] = roads
    df_geo['Latitude'] = lats
    df_geo['Longitude'] = lons
    
    # 4. 저장 (컬럼 순서 정리)
    cols = ['연번', '위험지구명', '대표지번(위치)', '정규화_지번주소', '도로명_주소', 'Latitude', 'Longitude']
    # 원본 파일의 다른 컬럼들도 유지할 경우 아래 코드로 실행
    # df_geo.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    df_geo.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"\n\n[{time.strftime('%H:%M:%S')}] 완료되었습니다!")
    print(f"- 파일명: {output_file}")
    print(f"- 도로명 변환 성공: {df_geo['도로명_주소'].notna().sum()}건")

if __name__ == "__main__":
    main()