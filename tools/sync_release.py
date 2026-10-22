#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 hinlink-out 下的镜像同步成 release 的全部 asset（删旧 + 传新）。

为什么要这么写：构建机到 GitHub 的连接今晚很不稳（TLS reset），
publish_release.py 的 curl 只 retry 3 次且不带 --retry-all-errors。
这里改成：
  · 所有 API 调用带指数退避重试；
  · 上传用 curl --retry 8 --retry-delay 5 --retry-all-errors；
  · 整体按「缺什么传什么」循环，最多 20 轮，断了重跑也不会重复传。
"""
import os
import sys
import json
import time
import glob
import hashlib
import subprocess
import socket
import urllib.request
import urllib.error

# ★ 构建机到 GitHub 的 IPv6 路径是坏的（TLS 握手直接 reset），
#   而 IPv4 实测 3 MB/s 以上。urllib 不会自己回退，这里直接只解析 A 记录。
_gai = socket.getaddrinfo


def _gai_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _gai(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _gai_ipv4

TOKEN = os.environ["GH_TOKEN"]
REPO = os.environ["REPO"]
TAG = os.environ["TAG"]
OUT = os.environ.get("HINLINK_OUT", os.path.expanduser("~/hinlink-out-xwrt"))
BODY_FILE = os.environ.get("BODY_FILE")
API = "https://api.github.com/repos/%s" % REPO


def api(method, url, data=None, tries=20):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, method=method)
            req.add_header("Authorization", "token " + TOKEN)
            req.add_header("Accept", "application/vnd.github+json")
            if data is not None:
                req.data = json.dumps(data).encode()
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, {}
        except Exception as e:                      # 连接被 reset 之类
            last = e
            time.sleep(min(60, 5 * (i + 1)))
    print("  !! api %s %s 失败: %s" % (method, url, last), flush=True)
    return 0, {}


def list_assets(rid):
    st, r = api("GET", "%s/releases/%d/assets?per_page=100" % (API, rid))
    return r if isinstance(r, list) else None


def gen_sums(files):
    p = os.path.join(OUT, "sha256sums.txt")
    with open(p, "w", encoding="utf-8") as fh:
        for f in sorted(files):
            h = hashlib.sha256()
            with open(f, "rb") as g:
                for b in iter(lambda: g.read(1 << 20), b""):
                    h.update(b)
            fh.write("%s  %s\n" % (h.hexdigest(), os.path.basename(f)))
    return p


def upload(rid, path, name):
    url = ("https://uploads.github.com/repos/%s/releases/%d/assets?name=%s"
           % (REPO, rid, name))
    cmd = ["curl", "-4", "-sS", "--retry", "8", "--retry-delay", "5",
           "--retry-all-errors", "--connect-timeout", "30",
           "--speed-limit", "20480", "--speed-time", "60",
           "--max-time", "900", "-X", "POST",
           "-H", "Expect:",
           "-H", "Authorization: token " + TOKEN,
           "-H", "Content-Type: application/octet-stream",
           "--data-binary", "@" + path, url]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True)
    try:
        j = json.loads(r.stdout or "{}")
    except Exception:
        j = {"raw": (r.stdout or "")[:200]}
    return r.returncode, j


def main():
    st, rel = api("GET", "%s/releases/tags/%s" % (API, TAG))
    if st != 200:
        sys.exit("拿不到 release: HTTP %s" % st)
    rid = rel["id"]
    print("release id=%s  %s" % (rid, rel.get("html_url")), flush=True)

    if BODY_FILE and os.path.exists(BODY_FILE):
        st, r = api("PATCH", "%s/releases/%d" % (API, rid),
                    {"body": open(BODY_FILE, encoding="utf-8").read()})
        print("说明 patch: %s（%d 字节）" % (st, len(r.get("body", ""))), flush=True)

    if os.environ.get("SYNC_PURGE", "1") == "1":
        for rnd in range(1, 11):
            cur = list_assets(rid)
            if cur is None:
                print("  列表拿不到，20s 后重试（第 %d 轮）" % rnd, flush=True)
                time.sleep(20)
                continue
            if not cur:
                print("旧 asset 已清空", flush=True)
                break
            print("第 %d 轮清除：还剩 %d 个" % (rnd, len(cur)), flush=True)
            for a in cur:
                s, _ = api("DELETE", "%s/releases/assets/%d" % (API, a["id"]), tries=8)
                if s not in (204, 404):
                    print("  ? 删除失败 %s HTTP %s" % (a["name"], s), flush=True)
            time.sleep(3)
    else:
        print("SYNC_PURGE=0：跳过删除，只补缺", flush=True)

    files = sorted(glob.glob(os.path.join(OUT, "*", "*.img.gz")))
    if not files:
        sys.exit("在 %s 下没找到 *.img.gz" % OUT)
    files.append(gen_sums(files))
    print("待上传 %d 个文件 / %.1f MB"
          % (len(files), sum(os.path.getsize(f) for f in files) / 1048576.0), flush=True)

    for rnd in range(1, 21):
        have = {a["name"] for a in (list_assets(rid) or [])}
        todo = [f for f in files if os.path.basename(f) not in have]
        if not todo:
            print("\n全部就位：%d 个 asset" % len(have), flush=True)
            return
        print("\n[第 %d 轮] 还差 %d 个" % (rnd, len(todo)), flush=True)
        for f in todo:
            name = os.path.basename(f)
            sz = os.path.getsize(f) / 1048576.0
            print("  上传 %-72s %7.1f MB ..." % (name, sz), end="", flush=True)
            rc, j = upload(rid, f, name)
            if rc == 0 and j.get("name"):
                print(" OK", flush=True)
            else:
                print(" 失败 rc=%s %s" % (rc, str(j)[:120]), flush=True)
            time.sleep(1)

    print("\n20 轮后仍未完成，剩下的：", flush=True)
    have = {a["name"] for a in (list_assets(rid) or [])}
    for f in files:
        if os.path.basename(f) not in have:
            print("  MISS", os.path.basename(f), flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
