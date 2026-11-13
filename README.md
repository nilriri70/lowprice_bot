# 🤖 LowPrice Bot (베베앙 20개 최저가 알림 봇)

다나와 쇼핑 검색을 통해 **"베베앙 20개"** 최저가 상품을 실시간 검색하고, 광고를 제외한 상위 3개 상품을 출력하며, 1위 상품이 목표가(20,000원) 이하일 때 카카오톡 "나에게 보내기"로 특가 알림을 전송하는 봇입니다.

## 📌 주요 기능
1. **다나와 실시간 최저가 순 검색 (`sort=priceASC`)**:
   - 다나와 가격비교 API를 연동하여 실시간 최저가, 판매 쇼핑몰, 배송비 및 리뷰 수 추출
2. **광고 상품 필터링**:
   - `AD`, `파워클릭`, 광고 배지 및 비관련 품목 자동 필터링
3. **목표가 판정 및 카카오톡 특가 알림**:
   - 1위 가격이 20,000원 이하일 때: `[특가발견]` 판정 및 카카오톡 '나에게 보내기' 메시지 발송 (구매 링크 버튼 포함)
   - 1위 가격이 20,000원 초과일 때: `[유지]` 판정 (메시지 미발송)
4. **엄격한 에러 핸들링**:
   - 문제 발생 시 지어내지 않고 원인 에러를 명확히 출력

## 🚀 설치 및 사용법

### 1. 패키지 설치
```bash
pip install beautifulsoup4
```

### 2. 환경변수 설정 (`.env`)
`.env` 파일에 카카오 인증 정보를 설정합니다:
```properties
KAKAO_REST_API_KEY=your_rest_api_key
KAKAO_CLIENT_SECRET=your_client_secret
KAKAO_REFRESH_TOKEN=your_refresh_token
```

### 3. 실행
```bash
python lowprice_bot.py
```

### 4. 단위 테스트 실행
```bash
python test_lowprice_bot.py
```
