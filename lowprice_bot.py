#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lowprice_bot.py
다나와 쇼핑 검색을 통해 '베베앙 20개' 최저가 상품을 찾고, 목표가 도달 여부를 알려주는 봇
"""

import sys
import re
import json
import time
import urllib.request
import urllib.parse
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional

# Windows 콘솔 한글 깨짐 방지
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr.encoding != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[오류] beautifulsoup4 라이브러리가 필요합니다. 'pip install beautifulsoup4'를 실행해주세요.", file=sys.stderr)
    sys.exit(1)

# 설정값
ENV_PATH = Path(__file__).parent / ".env"
TARGET_KEYWORD = "베베앙 20개"
TARGET_PRICE = 20000  # 목표 가격 (원)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"


def load_kakao_env() -> Dict[str, str]:
    """.env 파일에서 카카오 인증 정보를 안전하게 로드합니다."""
    env_vars = {}
    if not ENV_PATH.exists():
        return env_vars
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip("'\"")
    return env_vars


def get_kakao_access_token(env_vars: Dict[str, str]) -> str:
    """리프레시 토큰을 사용하여 카카오 액세스 토큰을 갱신 발급받습니다."""
    client_id = env_vars.get("KAKAO_REST_API_KEY")
    client_secret = env_vars.get("KAKAO_CLIENT_SECRET")
    refresh_token = env_vars.get("KAKAO_REFRESH_TOKEN")

    if not client_id or not refresh_token:
        missing = []
        if not client_id:
            missing.append("KAKAO_REST_API_KEY")
        if not refresh_token:
            missing.append("KAKAO_REFRESH_TOKEN")
        raise ValueError(f".env 파일에 필수 카카오 인증 정보({', '.join(missing)})가 누락되었습니다.")

    token_url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    if client_secret:
        payload["client_secret"] = client_secret

    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        token_url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            access_token = data.get("access_token")
            if not access_token:
                raise ValueError(f"카카오 토큰 응답에 access_token이 없습니다: {data}")

            # 리프레시 토큰이 함께 재발급된 경우 .env 업데이트
            new_refresh = data.get("refresh_token")
            if new_refresh and new_refresh != refresh_token:
                update_env_refresh_token(new_refresh)

            return access_token
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        raise RuntimeError(f"카카오 액세스 토큰 갱신 실패 (HTTP {e.code}): {err_body}") from e
    except Exception as e:
        raise RuntimeError(f"카카오 토큰 요청 중 오류 발생: {e}") from e


def update_env_refresh_token(new_refresh_token: str):
    """.env 파일의 KAKAO_REFRESH_TOKEN 항목을 갱신합니다."""
    try:
        lines = []
        if ENV_PATH.exists():
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        new_lines = []
        found = False
        for line in lines:
            if line.strip().startswith("KAKAO_REFRESH_TOKEN="):
                new_lines.append(f"KAKAO_REFRESH_TOKEN={new_refresh_token}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"KAKAO_REFRESH_TOKEN={new_refresh_token}\n")
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"[경고] .env 리프레시 토큰 갱신 저장 실패: {e}", file=sys.stderr)


def send_kakao_alert(item: Dict[str, Any]) -> bool:
    """
    1위 특가 상품 정보를 카카오톡 '나에게 보내기'로 전송합니다.
    실패 시 보낸 척하지 않고 구체적인 실패 원인을 명확히 출력합니다.
    """
    try:
        env_vars = load_kakao_env()
        access_token = get_kakao_access_token(env_vars)

        template = {
            "object_type": "text",
            "text": (
                f"🎉 [특가발견] 베베앙 20개 최저가 알림!\n\n"
                f"• 상품명: {item['title']}\n"
                f"• 가격: {item['price']:,}원\n"
                f"• 쇼핑몰: {item['mall']}\n"
                f"• 리뷰수: {item['reviews']:,}개"
            ),
            "link": {
                "web_url": item["link"],
                "mobile_web_url": item["link"]
            },
            "button_title": "구매하러 가기"
        }

        payload = {
            "template_object": json.dumps(template, ensure_ascii=False)
        }
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            data=encoded,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
            }
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("result_code") == 0:
                print(" >> 📱 [카카오톡 알림] 1위 특가 상품 알림이 카카오톡 '나에게 보내기'로 전송되었습니다!")
                return True
            else:
                print(f"\n❌ [카카오톡 알림 전송 실패] 카카오 응답 코드 오류: {res}", file=sys.stderr)
                return False

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"\n❌ [카카오톡 알림 전송 실패] 카카오 API 호출 실패 (HTTP {e.code}): {err_body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"\n❌ [카카오톡 알림 전송 실패] {type(e).__name__}: {e}", file=sys.stderr)
        return False


def fetch(url: str, *, method: str = "GET", data: Optional[dict] = None, referer: Optional[str] = None) -> str:
    """웹 페이지 또는 API 데이터를 안전하게 요청하여 반환합니다."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"
    if referer:
        headers["Referer"] = referer

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(f"[오류] 다나와 서버 요청 실패 (HTTP {e.code}): {url}", file=sys.stderr)
        print(f"상세 내용: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[오류] 네트워크 연결 실패: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[오류] 요청 중 알 수 없는 예외 발생: {type(e).__name__} - {e}", file=sys.stderr)
        sys.exit(1)


def js_value(html: str, key: str) -> str:
    """다나와 상품 상세 HTML에서 자바스크립트 변수 값을 추출합니다."""
    patterns = [
        rf"{re.escape(key)}\s*:\s*\"([^\"]*)\"",
        rf"{re.escape(key)}\s*:\s*'([^']*)'",
        rf"{re.escape(key)}\s*:\s*([0-9]+)",
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            raw = m.group(1)
            if "\\u" in raw or "\\/" in raw:
                try:
                    return json.loads('"' + raw.replace('"', '\\"') + '"')
                except Exception:
                    return raw.replace("\\/", "/")
            return raw
    return ""


def get_product_meta(pcode: str) -> Dict[str, str]:
    """상품 메타데이터를 수집합니다."""
    url = f"https://prod.danawa.com/info/?pcode={urllib.parse.quote(str(pcode))}"
    html = fetch(url)
    meta = {
        "pcode": str(pcode),
        "source_url": url,
        "cate1": js_value(html, "nCategoryCode1"),
        "cate2": js_value(html, "nCategoryCode2"),
        "cate3": js_value(html, "nCategoryCode3"),
        "cate4": js_value(html, "nCategoryCode4") or "0",
        "UICategoryCode": js_value(html, "nCategoryCode"),
        "powerLinkKeyword": js_value(html, "powerLinkKeyword"),
        "minPrice": js_value(html, "nMinPrice"),
        "keyword": js_value(html, "sKeyword"),
        "NaPm": js_value(html, "sNaPm"),
        "sProductFullName": js_value(html, "sProductName"),
        "makerCode": js_value(html, "makerCode"),
        "makerName": js_value(html, "makerName"),
    }
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(".prod_tit .title") or soup.title
    if title_el:
        full_title = title_el.get_text(" ", strip=True).split(" : 다나와")[0].strip()
        meta["sProductFullName"] = full_title or meta["sProductFullName"]
    return meta


def get_product_offers(pcode: str) -> List[Dict[str, Any]]:
    """다나와 AJAX 엔드포인트를 호출하여 해당 상품의 쇼핑몰별 실시간 가격 목록(오퍼)을 가져옵니다."""
    meta = get_product_meta(pcode)
    data = {
        "pcode": meta["pcode"],
        "cate1": meta.get("cate1", ""),
        "cate2": meta.get("cate2", ""),
        "cate3": meta.get("cate3", ""),
        "cate4": meta.get("cate4", "0"),
        "UICategoryCode": meta.get("UICategoryCode", "0"),
        "powerLinkKeyword": meta.get("powerLinkKeyword", ""),
        "minPrice": meta.get("minPrice", ""),
        "keyword": meta.get("keyword", ""),
        "NaPm": meta.get("NaPm", ""),
        "bDeliveryLeftRightYN": "N",
        "bQuickPostSortYN": "N",
        "sSortType": "minPrice",
        "sProductFullName": meta.get("sProductFullName", ""),
        "bPostPriceYN": "N",
        "bBadgeDefaultYN": "N",
        "bWarrantyDefaultYN": "N",
        "nOpenMarketMoreCount": "30",
        "nAffiliateMoreCount": "30",
        "nOverseasShoppingMoreCount": "30",
        "nGeneralAffiliateMoreCount": "3",
        "sRelationMenuType": "",
        "sRelationType": "",
        "bCoupangSortYN": "N",
        "makerCode": meta.get("makerCode", ""),
        "makerName": meta.get("makerName", ""),
    }

    ajax_url = "https://prod.danawa.com/info/ajax/getAllPriceCompareMallList.ajax.php"
    html = fetch(ajax_url, method="POST", data=data, referer=meta["source_url"])
    soup = BeautifulSoup(html, "html.parser")

    offers = []
    for div in soup.select(".diff_item"):
        mall_div = div.select_one(".d_mall")
        mall = None
        if mall_div:
            mall_img = mall_div.select_one("img")
            logo_span = mall_div.select_one(".txt_logo")
            if mall_img and mall_img.get("alt"):
                mall = mall_img.get("alt").strip()
            elif logo_span and logo_span.get_text(strip=True):
                mall = logo_span.get_text(strip=True)
            else:
                mall_clone = BeautifulSoup(str(mall_div), "html.parser").select_one(".d_mall")
                for noise in mall_clone.select(".report, .npay, .btn_rpt, [class*='report'], [class*='pay']"):
                    noise.decompose()
                mall_text = mall_clone.get_text(" ", strip=True)
                mall = re.sub(r"(네이버페이|신고|스마트스토어)", "", mall_text).strip() or mall_text

        price_el = div.select_one("em.prc_c") or div.select_one("em.prc_t")
        if not price_el:
            continue
        digits = re.sub(r"\D", "", price_el.get_text())
        if not digits:
            continue
        price = int(digits)

        link_el = div.select_one("a.priceCompareBuyLink")
        link = link_el.get("href") if link_el else meta["source_url"]
        if link.startswith("//"):
            link = "https:" + link

        offers.append({
            "mall": mall or "쇼핑몰 미확인",
            "price": price,
            "url": link,
        })

    offers.sort(key=lambda x: x["price"])
    return offers


def search_and_filter_products(query: str) -> List[Dict[str, Any]]:
    """
    다나와에서 검색어를 최저가 순으로 검색하고,
    광고 및 허수 상품을 필터링한 진짜 상품 목록을 반환합니다.
    """
    search_url = f"https://search.danawa.com/?query={urllib.parse.quote(query)}&sort=priceASC"
    html = fetch(search_url)
    soup = BeautifulSoup(html, "html.parser")

    # 상품 카드 추출 (신규 및 구형 다나와 구조 대응)
    product_cards = soup.select("li[data-product-seq]")
    if not product_cards:
        # 구형 구조 fallback
        product_cards = soup.select("li.prod_item")

    if not product_cards:
        print(f"[오류] 다나와 검색 결과에서 상품 목록을 파싱하지 못했습니다. (검색어: '{query}')", file=sys.stderr)
        print("다나와 웹사이트 구조가 변경되었거나 일시적으로 검색 결과가 비어 있을 수 있습니다.", file=sys.stderr)
        sys.exit(1)

    real_products = []

    for card in product_cards:
        pcode = card.get("data-product-seq")
        if not pcode:
            pid = (card.get("id") or "").replace("productItem", "")
            pcode = pid or None

        if not pcode:
            continue

        card_text = card.get_text(" ", strip=True)

        # 3. 광고 상품 필터링:
        # - 카드 내부나 태그 클래스에 명시된 광고 표시 검사
        is_ad = False
        if card.select(".ad, .badge-ad, [class*='ad_'], [class*='ad-'], .power_click, .power_link"):
            is_ad = True
        if re.search(r"\b(AD|광고|스폰서링크|파워클릭)\b", card_text):
            is_ad = True

        if is_ad:
            continue

        # 상품명 추출
        img_el = card.select_one(f"a[href*='pcode={pcode}'] img")
        title = img_el.get("alt", "").replace("<b>", "").replace("</b>", "").strip() if img_el else ""
        if not title:
            name_a = card.select_one(".prod_name a, p.prod_name a")
            if name_a:
                title = name_a.get_text(" ", strip=True)

        if not title:
            # 텍스트 내에서 후보 탐색
            for a in card.select(f"a[href*='pcode={pcode}']"):
                t = a.get_text(" ", strip=True)
                if t and t not in ["이미지 보기", "신고하기", "의견쓰기"] and "원" not in t and "리뷰수" not in t:
                    title = t
                    break

        if not title:
            # 상품명이 없으면 비정상 카드로 판단하고 제외
            continue

        # 검색어(베베앙)와의 유효성 검증
        if "베베앙" not in title:
            continue

        # 리뷰수 추출
        review_count = 0
        rev_m = re.search(r"리뷰수\s*\(\s*([\d,]+)\s*\)", card_text)
        if rev_m:
            try:
                review_count = int(rev_m.group(1).replace(",", ""))
            except ValueError:
                review_count = 0

        # 카드에 표기된 기준 최저가
        card_price = None
        prc_m = re.search(r"([\d,]+)원\s*[\d,]+\s*몰", card_text)
        if prc_m:
            card_price = int(prc_m.group(1).replace(",", ""))
        else:
            all_prices = [
                int(p.replace(",", ""))
                for p in re.findall(r"([\d,]+)원", card_text)
                if "원/10매" not in card_text[max(0, card_text.find(p) - 10):card_text.find(p) + len(p) + 10]
            ]
            if all_prices:
                card_price = all_prices[0]

        link = f"https://prod.danawa.com/info/?pcode={pcode}"

        real_products.append({
            "pcode": pcode,
            "title": title,
            "review_count": review_count,
            "card_price": card_price,
            "link": link,
        })

    if not real_products:
        print("[오류] 광고 필터링 후 유효한 진짜 상품이 0건입니다.", file=sys.stderr)
        sys.exit(1)

    return real_products


def run_lowprice_bot():
    """최저가 봇 메인 실행 로직"""
    print("=" * 68)
    print(f" 🤖 [LowPrice Bot] 다나와 '{TARGET_KEYWORD}' 최저가 검색 봇 가동")
    print(f" 🎯 목표 가격: {TARGET_PRICE:,}원 이하")
    print("=" * 68)
    print(">> 다나와 검색 결과 수집 및 광고 필터링 진행 중...\n")

    # 1. 최저가 순 검색 및 광고 필터링
    products = search_and_filter_products(TARGET_KEYWORD)

    final_top3 = []

    # 2. 상위 상품들의 실시간 최저가 오퍼 및 쇼핑몰 정보 확인
    for p in products:
        pcode = p["pcode"]
        offers = get_product_offers(pcode)

        if not offers:
            # 실시간 구매 가능한 쇼핑몰 오퍼가 전혀 없는 품절/허수 상품은 제외
            continue

        best_offer = offers[0]
        final_price = best_offer["price"]
        mall = best_offer["mall"]
        link = p["link"]

        # 상품명 상세 업데이트 (옵션 정보나 매수 등이 포함된 완전한 명칭)
        full_title = p["title"]

        final_top3.append({
            "rank": len(final_top3) + 1,
            "pcode": pcode,
            "title": full_title,
            "price": final_price,
            "mall": mall,
            "reviews": p["review_count"],
            "link": link,
        })

        if len(final_top3) >= 3:
            break

    # 유효성 검증
    if not final_top3:
        print("[오류] 실시간 구매 가능한 쇼핑몰 오퍼가 있는 상품을 찾지 못했습니다.", file=sys.stderr)
        sys.exit(1)

    # 2. 최저가 순서로 상품 3개 출력
    print("┌" + "─" * 66 + "┐")
    print("│                     📊 베베앙 20개 최저가 TOP 3                     │")
    print("└" + "─" * 66 + "┘\n")

    for item in final_top3:
        print(f" [{item['rank']}위] {item['title']}")
        print(f"  • 가격   : {item['price']:,}원")
        print(f"  • 쇼핑몰 : {item['mall']}")
        print(f"  • 리뷰수 : {item['reviews']:,}개")
        print(f"  • 링크   : {item['link']}")
        print("-" * 68)

    # 4. 1위 가격의 목표가 20,000원 이하 여부 판정 및 출력
    top_price = final_top3[0]["price"]
    top_title = final_top3[0]["title"]

    print("\n" + "=" * 68)
    print(f" 📢 [목표가 판정 결과] (1위: {top_title} / {top_price:,}원)")
    if top_price <= TARGET_PRICE:
        print(f" >> [특가발견] 목표 가격 이하입니다! (목표가: {TARGET_PRICE:,}원 / 현재가: {top_price:,}원)")
        print(" >> 🔔 목표 가격 이하이므로 카카오톡 알림을 전송합니다...")
        send_kakao_alert(final_top3[0])
    else:
        print(f" >> [유지] 아직 목표 가격 보다 비싸요! (목표가: {TARGET_PRICE:,}원 / 현재가: {top_price:,}원)")
        print(" >> ℹ️ 목표 가격을 초과하여 카카오톡 알림은 발송하지 않습니다.")
    print("=" * 68)


if __name__ == "__main__":
    try:
        run_lowprice_bot()
    except KeyboardInterrupt:
        print("\n[알림] 사용자에 의해 봇이 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[오류] 봇 실행 중 예기치 못한 문제가 발생했습니다: {type(e).__name__} - {e}", file=sys.stderr)
        sys.exit(1)
