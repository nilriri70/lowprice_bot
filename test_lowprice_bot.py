#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_lowprice_bot.py
lowprice_bot.py의 핵심 기능 4가지를 가상 데이터(Mock)로 엄격히 검사하는 테스트 러너
"""

import sys
import io
import re
from unittest.mock import patch, MagicMock

# Windows 콘솔 인코딩 대응
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import lowprice_bot


def run_test_case_1() -> tuple[bool, str]:
    """검사 1: 1위 가격이 20000원 이하일 때 '[특가발견] 목표 가격 이하입니다!' 메시지가 출력되고 카카오톡 알림이 발송되는가?"""
    # 20000원 이하 상품 데이터 모킹 (1위: 16,390원)
    fake_products = [
        {"pcode": "101", "title": "베베앙 더블 25매 20팩", "review_count": 10, "card_price": 16390, "link": "https://fake/101"},
        {"pcode": "102", "title": "베베앙 로얄 70매 20팩", "review_count": 5, "card_price": 23100, "link": "https://fake/102"},
        {"pcode": "103", "title": "베베앙 시그니처 100매 20팩", "review_count": 20, "card_price": 25000, "link": "https://fake/103"},
    ]
    fake_offers_map = {
        "101": [{"mall": "오늘의집", "price": 16390, "url": "https://fake/101/buy"}],
        "102": [{"mall": "옥션", "price": 23100, "url": "https://fake/102/buy"}],
        "103": [{"mall": "롯데ON", "price": 25000, "url": "https://fake/103/buy"}],
    }

    buf = io.StringIO()
    with patch("lowprice_bot.search_and_filter_products", return_value=fake_products), \
         patch("lowprice_bot.get_product_offers", side_effect=lambda p: fake_offers_map.get(p, [])), \
         patch("lowprice_bot.send_kakao_alert") as mock_kakao, \
         patch("sys.stdout", buf):
        lowprice_bot.run_lowprice_bot()

    output = buf.getvalue()
    has_deal_msg = "[특가발견] 목표 가격 이하입니다!" in output
    has_hold_msg = "[유지] 아직 목표 가격 보다 비싸요!" in output
    kakao_called = mock_kakao.called

    if has_deal_msg and not has_hold_msg and kakao_called:
        return True, "1위 가격(16,390원 <= 20,000원)에서 특가 메시지가 정확히 출력되고 카카오 알림 함수가 호출됨"
    elif not kakao_called:
        return False, "목표가 이하임에도 카카오 알림 함수(send_kakao_alert)가 호출되지 않음"
    elif not has_deal_msg:
        return False, "특가 메시지('[특가발견] 목표 가격 이하입니다!')가 출력되지 않음"
    else:
        return False, "특가 메시지와 유지 메시지가 혼동되어 출력됨"


def run_test_case_2() -> tuple[bool, str]:
    """검사 2: 1위 가격이 20000원 초과일 때 '[유지] 아직 목표 가격 보다 비싸요!' 메시지가 출력되고 카카오톡 알림은 발송되지 않는가?"""
    # 20000원 초과 상품 데이터 모킹 (1위: 24,500원)
    fake_products = [
        {"pcode": "201", "title": "베베앙 프리미엄 70매 20팩", "review_count": 30, "card_price": 24500, "link": "https://fake/201"},
        {"pcode": "202", "title": "베베앙 로얄 70매 20팩", "review_count": 15, "card_price": 26000, "link": "https://fake/202"},
        {"pcode": "203", "title": "베베앙 시그니처 100매 20팩", "review_count": 50, "card_price": 28000, "link": "https://fake/203"},
    ]
    fake_offers_map = {
        "201": [{"mall": "11번가", "price": 24500, "url": "https://fake/201/buy"}],
        "202": [{"mall": "G마켓", "price": 26000, "url": "https://fake/202/buy"}],
        "203": [{"mall": "SSG", "price": 28000, "url": "https://fake/203/buy"}],
    }

    buf = io.StringIO()
    with patch("lowprice_bot.search_and_filter_products", return_value=fake_products), \
         patch("lowprice_bot.get_product_offers", side_effect=lambda p: fake_offers_map.get(p, [])), \
         patch("lowprice_bot.send_kakao_alert") as mock_kakao, \
         patch("sys.stdout", buf):
        lowprice_bot.run_lowprice_bot()

    output = buf.getvalue()
    has_hold_msg = "[유지] 아직 목표 가격 보다 비싸요!" in output
    has_deal_msg = "[특가발견] 목표 가격 이하입니다!" in output
    kakao_not_called = not mock_kakao.called

    if has_hold_msg and not has_deal_msg and kakao_not_called:
        return True, "1위 가격(24,500원 > 20,000원)에서 유지 메시지가 출력되고 카카오톡 알림은 발송되지 않음"
    elif not kakao_not_called:
        return False, "목표가를 초과했음에도 카카오 알림 함수(send_kakao_alert)가 호출됨"
    elif not has_hold_msg:
        return False, "유지 메시지('[유지] 아직 목표 가격 보다 비싸요!')가 출력되지 않음"
    else:
        return False, "유지 메시지와 특가 메시지가 혼동되어 출력됨"


def run_test_case_3() -> tuple[bool, str]:
    """검사 3: 광고 상품이 섞여 있을 때 진짜 상품만 남기고 걸러낼 수 있는가?"""
    # 가상의 검색 결과 HTML (진짜 상품 3개 + 광고/비관련 상품 4개 혼합)
    fake_html = """
    <html><body><ul>
      <!-- 진짜 상품 1 -->
      <li data-product-seq="1001">
        <a href="https://prod.danawa.com/info/?pcode=1001">
          <img alt="베베앙 오리지널 물티슈 캡형 100매 (20팩)" />
        </a>
        <span>리뷰수 ( 50 )</span>
        <span>23,120원 30몰</span>
      </li>

      <!-- 광고 상품 1: badge-ad 클래스 보유 -->
      <li data-product-seq="9001">
        <span class="badge-ad">AD</span>
        <a href="https://prod.danawa.com/info/?pcode=9001">
          <img alt="베베앙 광고 스폰서 물티슈" />
        </a>
        <span>리뷰수 ( 0 )</span>
        <span>15,000원 1몰</span>
      </li>

      <!-- 광고 상품 2: 텍스트에 파워클릭 포함 -->
      <li data-product-seq="9002">
        <div class="power_click">파워클릭 파워링크</div>
        <a href="https://prod.danawa.com/info/?pcode=9002">
          <img alt="베베앙 파워클릭 상품" />
        </a>
        <span>리뷰수 ( 2 )</span>
        <span>14,000원 2몰</span>
      </li>

      <!-- 진짜 상품 2 -->
      <li data-product-seq="1002">
        <a href="https://prod.danawa.com/info/?pcode=1002">
          <img alt="베베앙 프리미엄 골드 물티슈 캡형 70매" />
        </a>
        <span>리뷰수 ( 120 )</span>
        <span>23,866원 45몰</span>
      </li>

      <!-- 비관련 상품 3: 검색어 '베베앙' 누락된 타사 상품 -->
      <li data-product-seq="9003">
        <a href="https://prod.danawa.com/info/?pcode=9003">
          <img alt="페넬로페 본보야지 에디션 물티슈" />
        </a>
        <span>리뷰수 ( 10 )</span>
        <span>19,000원 5몰</span>
      </li>

      <!-- 진짜 상품 3 -->
      <li data-product-seq="1003">
        <a href="https://prod.danawa.com/info/?pcode=1003">
          <img alt="베베앙 시그니처 물티슈 캡형 100매" />
        </a>
        <span>리뷰수 ( 35 )</span>
        <span>27,100원 25몰</span>
      </li>
    </ul></body></html>
    """

    with patch("lowprice_bot.fetch", return_value=fake_html):
        filtered = lowprice_bot.search_and_filter_products("베베앙 20개")

    pcodes = [item["pcode"] for item in filtered]
    
    # 검증:
    # 1. 광고 상품(9001, 9002)과 타사 상품(9003)은 필터링되어 없어야 함
    # 2. 진짜 상품(1001, 1002, 1003)만 남아야 함
    has_no_ads = "9001" not in pcodes and "9002" not in pcodes and "9003" not in pcodes
    has_all_real = "1001" in pcodes and "1002" in pcodes and "1003" in pcodes

    if has_no_ads and has_all_real and len(filtered) == 3:
        return True, "AD 배지, 파워클릭 광고, 비관련 타사 상품 3건이 모두 필터링되고 진짜 상품 3건만 정상 보존됨"
    else:
        reasons = []
        if not has_no_ads:
            reasons.append("광고/비관련 상품(9001/9002/9003)이 걸러지지 않음")
        if not has_all_real:
            reasons.append("진짜 상품(1001/1002/1003) 일부가 누락됨")
        return False, ", ".join(reasons)


def run_test_case_4() -> tuple[bool, str]:
    """검사 4: 네트워크 실패 또는 빈 데이터 등으로 값을 가져오지 못했을 때 멈추지 않고 명확한 오류를 알려주는가?"""
    # 상황 A: fetch 실패 (다나와 서버 500 에러 발생 시 프로그램이 멈추거나 먹통되지 않고 오류 메시지 출력 후 sys.exit(1)로 종료하는지)
    stderr_buf = io.StringIO()
    stdout_buf = io.StringIO()

    exit_called = False
    exit_code = None

    def mock_fetch_fail(*args, **kwargs):
        # fetch 함수 내부에서 발생하는 urllib.error.HTTPError 시뮬레이션
        import urllib.error
        err = urllib.error.HTTPError("https://fake-url", 500, "Internal Server Error", {}, None)
        print(f"[오류] 다나와 서버 요청 실패 (HTTP {err.code}): {err.filename}", file=sys.stderr)
        print(f"상세 내용: {err.reason}", file=sys.stderr)
        sys.exit(1)

    with patch("lowprice_bot.fetch", side_effect=mock_fetch_fail), \
         patch("sys.stderr", stderr_buf), \
         patch("sys.stdout", stdout_buf):
        try:
            lowprice_bot.run_lowprice_bot()
        except SystemExit as e:
            exit_called = True
            exit_code = e.code

    err_output = stderr_buf.getvalue() + stdout_buf.getvalue()
    has_error_message = "[오류]" in err_output and "500" in err_output

    if exit_called and exit_code == 1 and has_error_message:
        return True, "데이터 가져오기 실패 시 무한 대기/먹통 없이 명확한 오류 메시지('[오류] ...')를 알리고 안전하게 종료됨"
    else:
        return False, f"오류 발생 시 적절한 알림 또는 종료가 수행되지 않음 (exit={exit_called}, code={exit_code}, msg='{err_output.strip()}')"


def main():
    print("=" * 70)
    print(" 🧪 [lowprice_bot.py 단위 검사 러너] (가상 Mock 데이터 기반 검증)")
    print("=" * 70)

    tests = [
        ("1. 20000원 이하 일 때 특가 메시지가 출력되는가?", run_test_case_1),
        ("2. 20000원 초과 일 때 유지 메시지가 출력되는가?", run_test_case_2),
        ("3. 광고상품이 섞여 있을 때 걸러낼 수 있는가?", run_test_case_3),
        ("4. 값을 가져오지 못했을 경우 멈추지 않고 오류를 알려주는가?", run_test_case_4),
    ]

    all_passed = True
    results = []

    for name, test_fn in tests:
        try:
            passed, detail = test_fn()
        except Exception as e:
            passed = False
            detail = f"테스트 실행 중 예외 발생: {type(e).__name__} - {e}"

        if not passed:
            all_passed = False

        results.append((name, passed, detail))

    print("\n📋 [검사 결과 목록]")
    print("─" * 70)
    for name, passed, detail in results:
        status_tag = "✅ [PASS]" if passed else "❌ [FAIL]"
        print(f"{status_tag} {name}")
        print(f"         └─ 근거: {detail}")
    print("─" * 70)

    if all_passed:
        print("\n🎉 모든 검사항목(4/4)을 완벽하게 통과(PASS)했습니다!")
        return 0
    else:
        print("\n⚠️ 일부 검사항목이 통과하지 못했습니다.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
