#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get_from_url.py
전체 리다이렉트 URL에서 code와 redirect_uri를 자동 추출하여
카카오 토큰을 발급받고 .env에 저장하는 스크립트
"""

import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

# Windows 콘솔 인코딩 대응
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

ENV_PATH = Path("c:/ageapp/lowprice/.env")


def load_env(path: Path) -> dict:
    vars_dict = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    vars_dict[k.strip()] = v.strip().strip("'\"")
    return vars_dict


def process_url(full_url: str):
    parsed = urllib.parse.urlparse(full_url)
    params = urllib.parse.parse_qs(parsed.query)

    if "code" not in params:
        print("[오류] 입력된 URL에 '?code=' 인가 코드가 없습니다.", file=sys.stderr)
        sys.exit(1)

    code = params["code"][0]
    
    # redirect_uri 추출: 카카오 개발자 콘솔에는 일반적으로 끝에 슬래시가 없는 형태로 등록됩니다.
    # 예: http://localhost
    raw_path = parsed.path.rstrip("/")
    base_no_slash = f"{parsed.scheme}://{parsed.netloc}{raw_path}"
    
    # 슬래시 없는 형태를 무조건 1순위로 시도
    uris_to_try = [base_no_slash, base_no_slash + "/"]

    env_vars = load_env(ENV_PATH)
    client_id = env_vars.get("KAKAO_REST_API_KEY")
    client_secret = env_vars.get("KAKAO_CLIENT_SECRET")

    token_url = "https://kauth.kakao.com/oauth/token"
    success = False

    for uri in uris_to_try:
        data = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": uri,
            "code": code,
            "client_secret": client_secret,
        }
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(
            token_url,
            data=encoded,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                refresh_token = res.get("refresh_token")
                access_token = res.get("access_token")

                # .env 파일에 KAKAO_REFRESH_TOKEN 저장
                lines = []
                if ENV_PATH.exists():
                    with open(ENV_PATH, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                new_lines = []
                found = False
                for line in lines:
                    if line.strip().startswith("KAKAO_REFRESH_TOKEN="):
                        new_lines.append(f"KAKAO_REFRESH_TOKEN={refresh_token}\n")
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    if new_lines and not new_lines[-1].endswith("\n"):
                        new_lines[-1] += "\n"
                    new_lines.append(f"KAKAO_REFRESH_TOKEN={refresh_token}\n")

                with open(ENV_PATH, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

                print("=" * 60)
                print("🎉 [카카오 토큰 발급 성공!]")
                print(f" • 사용된 Redirect URI : {uri}")
                print(f" • Refresh Token      : {refresh_token}")
                print(f" • Access Token       : {access_token}")
                print(f"💾 .env 파일에 KAKAO_REFRESH_TOKEN 저장을 완료했습니다!")
                print("=" * 60)
                success = True
                break
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8")
            if "KOE303" in err:
                continue
            else:
                print(f"[카카오 응답 오류] {err}", file=sys.stderr)
                break

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python get_from_url.py <전체_URL>")
        sys.exit(1)
    process_url(sys.argv[1].strip())
