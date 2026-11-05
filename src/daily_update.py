"""
Unattended daily update of the SWEET Basin Explorer.

Each run:
  1. finds season days in the last LOOKBACK_DAYS (through yesterday) that have
     no statewide statistics yet, so missed days are caught up and days whose
     data were not yet posted are retried on the next run;
  2. runs src.run_daily for each (SNODAS + UA SWE downloaded automatically;
     CU SWE used whenever data/CU_SWE/<date>_raster.tif exists);
  3. deletes that day's raw SNODAS / UA SWE files (kept if a weekly report
     folder exists for the date) and daily rasters older than KEEP_RASTER_DAYS,
     so nothing accumulates but the small statistics tables;
  4. rebuilds web/sweet_explorer.html and web/sweet_explorer_offline.html and,
     if PUBLISH_DIR is set, copies both there.

Log: data/logs/daily_update.log

Usage:
    python -m src.daily_update                  # normal daily run (Task Scheduler)
    python -m src.daily_update --since 20261001 # process every missing day since a date
    python -m src.daily_update --rebuild-only   # just rebuild/publish the page
"""
import argparse
import shutil
import sys
import traceback
from datetime import date, datetime, timedelta

import pandas as pd

import subprocess

def push_pages(pub_dir, label):
    """Replace the single gh-pages commit so the branch never accumulates history."""
    try:
        git = lambda *a: subprocess.run(["git", "-C", str(pub_dir), *a],
                                        check=True, capture_output=True, text=True)
        git("add", "-A")
        git("commit", "--amend", "-m", f"SWEET explorer {label}")
        git("push", "--force", "origin", "gh-pages")
        log.info("Published to GitHub Pages")
    except subprocess.CalledProcessError as e:
        log.warning(f"Pages push failed: {e.stderr}")

        push_pages(C.PUBLISH_DIR, datetime.date.today().isoformat())

from src import config as C
from src import build_web, run_daily, sources
from src.climatology import dowy

LOG = C.DATA_DIR / "logs" / "daily_update.log"


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def in_season(d):
    s, e = C.SEASON_START, C.SEASON_END
    md = (d.month, d.day)
    return md >= s or md <= e          # season spans the new year (Oct 1 - Jul 31)


def processed_dates(wy):
    """Dates already produced by the daily run (report imports don't count)."""
    f = C.STATS_DIR / "current" / f"WY{wy}_ensemble.parquet"
    if not f.exists():
        return set()
    e = pd.read_parquet(f, columns=None)
    if "source" in e:
        e = e[e["source"].isna() | ~e["source"].astype(str).str.contains("report", case=False)]
    return set(e["date"].dt.strftime("%Y%m%d"))


def pending_dates(since=None, until=None):
    until = until or date.today() - timedelta(days=1)
    start = since or until - timedelta(days=C.LOOKBACK_DAYS - 1)
    done = {}
    out, d = [], start
    while d <= until:
        s = d.strftime("%Y%m%d")
        wy = sources.water_year(s)
        if wy not in done:
            done[wy] = processed_dates(wy)
        if in_season(d) and s not in done[wy]:
            out.append(s)
        d += timedelta(days=1)
    return out


def cleanup(d):
    report_dir = C.BASE_DIR / "reports" / f"{d[:4]}-{d[4:6]}-{d[6:]}"
    if not report_dir.exists():           # keep raw files used by a weekly report
        for p in (sources.snodas_path(d), sources.uaswe_path(d)):
            p.unlink(missing_ok=True)
    cutoff = (date.today() - timedelta(days=C.KEEP_RASTER_DAYS)).strftime("%Y%m%d")
    rdir = C.DATA_DIR / "rasters"
    if rdir.exists():
        for sub in rdir.iterdir():
            if sub.is_dir() and sub.name.isdigit() and sub.name < cutoff:
                shutil.rmtree(sub, ignore_errors=True)


def rebuild_and_publish(wy):
    build_web.build(wy, offline=True)
    if C.PUBLISH_DIR:
        dest = C.PUBLISH_DIR
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("sweet_explorer.html", "sweet_explorer_offline.html"):
            shutil.copy2(C.WEB_DIR / name, dest / name)
        log(f"published to {dest}")


def update(since=None, keep_raw=False, rebuild_only=False):
    yesterday = date.today() - timedelta(days=1)
    wy = sources.water_year(yesterday.strftime("%Y%m%d"))
    n_ok = 0
    if not rebuild_only:
        todo = pending_dates(since)
        log(f"pending: {todo or 'none'}")
        for d in todo:
            try:
                run_daily.run(d)
                n_ok += 1
                log(f"{d}: done")
            except (sources.DataUnavailable, RuntimeError) as e:
                log(f"{d}: not available yet ({e}); will retry on the next run")
                continue
            except Exception:                                   # noqa: BLE001
                log(f"{d}: FAILED\n{traceback.format_exc()}")
                continue
            if not keep_raw:
                cleanup(d)
    if n_ok or rebuild_only:
        if (C.STATS_DIR / "current" / f"WY{wy}_ensemble.parquet").exists():
            rebuild_and_publish(wy)
            log(f"page rebuilt for WY{wy}")
        else:
            log(f"no WY{wy} statistics yet; page not rebuilt")
    return n_ok


def update_for_report(report_date):
    """Called at the end of generate_report.py: add the report date statewide
    (reusing the files the report just downloaded), then rebuild/publish."""
    run_daily.run(report_date)
    rebuild_and_publish(sources.water_year(report_date))
    log(f"{report_date}: statewide update from generate_report.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", help="YYYYMMDD: process every missing season day since this date")
    ap.add_argument("--keep-raw", action="store_true", help="keep downloaded SNODAS/UA files")
    ap.add_argument("--rebuild-only", action="store_true")
    a = ap.parse_args()
    since = datetime.strptime(a.since, "%Y%m%d").date() if a.since else None
    try:
        update(since, a.keep_raw, a.rebuild_only)
    except Exception:                                           # noqa: BLE001
        log(f"daily update FAILED\n{traceback.format_exc()}")
        sys.exit(1)
