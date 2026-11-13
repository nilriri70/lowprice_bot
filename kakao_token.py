#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kakao_token.py
카카오 인가 코드를 이용해 액세스 토큰 및 리프레시 토큰을 발급받고,
.env 파일에 KAKAO_REFRESH_TOKEN을 자동으로 저장/갱신하는 스크립트
"""

import os
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

ENV_PATH = Path(__file__).parent / ".env"


def load_env(env_path: Path) -> dict:
    """간단한 .env 파서"""
    env_vars = {}
    if not env_path.exists():
        return env_vars
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip("'\"")
    return env_vars


def save_refresh_token_to_env(env_path: Path, refresh_token: str):
    """.env 파일에 KAKAO_REFRESH_TOKEN 항목을 추가하거나 기존 값을 교체합니다."""
    lines = []
    found = False
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith("KAKAO_REFRESH_TOKEN="):
            new_lines.append(f"KAKAO_REFRESH_TOKEN={refresh_token}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        # 파일 끝에 줄바꿈이 없으면 줄바꿈 추가
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"KAKAO_REFRESH_TOKEN={refresh_token}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def issue_token(code: str, redirect_uri: str) -> dict:
    """카카오 OAuth 토큰 발급 요청"""
    env_vars = load_env(ENV_PATH)
    client_id = env_vars.get("KAKAO_REST_API_KEY")
    client_secret = env_vars.get("KAKAO_CLIENT_SECRET")

    if not client_id:
        print("[오류] .env 파일에 KAKAO_REST_API_KEY가 정의되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    if client_secret:
        payload["client_secret"] = client_secret

    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
            err_code = err_json.get("error_code", "UNKNOWN")
            err_desc = err_json.get("error_description", err_body)
        except Exception:
            err_code = f"HTTP_{e.code}"
            err_desc = err_body

        print(f"\n❌ [카카오 토큰 발급 실패] {err_code}: {err_desc}", file=sys.stderr)
        if err_code == "KOE320":
            print("👉 원인: 인가 코드가 이미 사용되었거나, 발급 후 유효 시간(수 분)이 만료되었습니다.", file=sys.stderr)
            print("👉 해결: 브라우저에서 인가 코드를 새로 발급받아 다시 시도해주세요.", file=sys.stderr)
        elif err_code == "KOE303":
            print(f"👉 원인: 요청한 redirect_uri('{redirect_uri}')가 인가 코드를 받을 때 사용한 Redirect URI와 일치하지 않습니다.", file=sys.stderr)
            print("👉 해결: 카카오 로그인창을 띄울 때 사용했던 Redirect URI와 정확히 일치시켜 입력해주세요.", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("사용법: python kakao_token.py <인가코드> [redirect_uri]")
        sys.exit(1)

    code = sys.argv[1].strip()
    redirect_uri = sys.argv[2].strip() if len(sys.argv) >= 3 else "https://localhost:5000"

    print("=" * 60)
    print(" 🔑 카카오 OAuth 토큰 발급 및 .env 저장 유틸리티")
    print(f" • 인가코드: {code[:15]}...{code[-10:]}")
    print(f" • Redirect URI: {redirect_uri}")
    print("=" * 60)

    token_data = issue_token(code, redirect_uri)
    refresh_token = token_data.get("refresh_token")
    access_token = token_data.get("access_token")

    if not refresh_token:
        print("❌ [오류] 응답에 refresh_token이 포함되어 있지 않습니다.", file=sys.stderr)
        print(token_data, file=sys.stderr)
        sys.exit(1)

    print("\n✅ 토큰 발급 성공!")
    print(f" • Access Token  : {access_token[:15]}... (유효시간: {token_data.get('expires_in')}초)")
    print(f" • Refresh Token : {refresh_token[:15]}... (유효시간: {token_data.get('refresh_token_expires_in')}초)")

    # .env 파일에 저장
    save_refresh_token_to_env(ENV_PATH, refresh_token)
    print(f"\n💾 .env 파일에 'KAKAO_REFRESH_TOKEN' 항목이 성공적으로 저장되었습니다.")


if __name__ == "__main__":
    main()
