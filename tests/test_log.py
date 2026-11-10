"""Logs: un fichero por día (BubbleQuest_AAAAMMDD.log), se conservan los 10 últimos."""

import logging
import os
from datetime import date, datetime

from orbes.log import KEEP_FILES, DailyFileHandler, log_file_for, remove_old_logs, setup_logging


def test_log_file_name_uses_date():
    assert log_file_for("x", date(2026, 11, 10)).name == "BubbleQuest_20261110.log"


def test_remove_old_logs_keeps_the_ten_most_recent_files(tmp_path):
    days = [date(2026, 1, 1), date(2026, 3, 5), date(2026, 3, 6)] + \
        [date(2026, 10, d) for d in range(1, 11)]             # 13 logs, no seguidos
    for day in days:
        log_file_for(tmp_path, day).write_text("x")
    for name in ("BubbleQuest_notadate.log", "BubbleQuest_20261340.log", "otro.log"):
        (tmp_path / name).write_text("x")                     # no son logs diarios: no se tocan
    removed = remove_old_logs(tmp_path)
    assert KEEP_FILES == 10
    assert [p.name for p in removed] == ["BubbleQuest_20260101.log", "BubbleQuest_20260305.log",
                                         "BubbleQuest_20260306.log"]
    kept = sorted(p.name for p in tmp_path.glob("BubbleQuest_2026????.log")
                  if p.name != "BubbleQuest_20261340.log")
    assert kept == [f"BubbleQuest_202610{d:02d}.log" for d in range(1, 11)]
    for name in ("BubbleQuest_notadate.log", "BubbleQuest_20261340.log", "otro.log"):
        assert (tmp_path / name).exists()


def test_old_logs_far_apart_are_kept_if_among_the_last_ten(tmp_path):
    for year in range(2020, 2026):                            # 6 logs, uno por año
        log_file_for(tmp_path, date(year, 1, 1)).write_text("x")
    assert remove_old_logs(tmp_path) == []


def test_daily_handler_switches_file_at_midnight(tmp_path):
    handler = DailyFileHandler(tmp_path)
    handler.day = date(2026, 10, 15)             # simulamos que la app arrancó ayer
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hola", None, None)
    record.created = datetime(2026, 10, 16, 0, 0, 5).timestamp()
    handler.emit(record)
    handler.close()
    assert (tmp_path / "BubbleQuest_20261016.log").read_text().strip() == "hola"


def test_setup_logging_writes_todays_file_and_prunes(tmp_path):
    for d in range(1, 13):                                    # 12 logs viejos
        log_file_for(tmp_path, date(2025, 1, d)).write_text("x")
    logger = logging.getLogger("orbes")
    saved = logger.handlers[:]
    logger.handlers.clear()
    try:
        setup_logging(log_dir=tmp_path)
        logging.getLogger("orbes.world").warning("aviso de prueba")
        for h in logger.handlers:
            h.flush()
        today = log_file_for(tmp_path, date.today())
        assert "aviso de prueba" in today.read_text(encoding="utf-8")
        assert len(list(tmp_path.glob("BubbleQuest_*.log"))) == KEEP_FILES
    finally:
        for h in logger.handlers:
            h.close()
        logger.handlers[:] = saved


def test_midnight_switch_also_leaves_exactly_ten(tmp_path):
    from datetime import timedelta
    today = date.today()
    for back in range(1, 11):                                 # 10 logs: de hace 10 días a ayer
        log_file_for(tmp_path, today - timedelta(days=back)).write_text("x")
    handler = DailyFileHandler(tmp_path)
    # Como si hubiera arrancado ayer: escribiendo en el fichero de ayer y sin fichero de hoy
    # (al crearse, el manejador abre el de hoy; en la vida real a medianoche aún no existe)
    handler.close()
    log_file_for(tmp_path, today).unlink()
    yesterday = today - timedelta(days=1)
    handler.baseFilename = os.path.abspath(log_file_for(tmp_path, yesterday))
    handler.day = yesterday                                   # arrancó ayer...
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "nuevo día", None, None)
    record.created = datetime.combine(today, datetime.min.time()).timestamp() + 5  # ...y pasa 00:00
    handler.emit(record)
    handler.close()
    names = sorted(p.name for p in tmp_path.glob("BubbleQuest_*.log"))
    assert len(names) == 10                                   # justo 10, contando el de hoy
    assert names[-1] == log_file_for(tmp_path, today).name
    assert log_file_for(tmp_path, today - timedelta(days=10)).name not in names
    assert "nuevo día" in log_file_for(tmp_path, today).read_text(encoding="utf-8")
