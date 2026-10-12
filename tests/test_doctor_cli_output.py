from __future__ import annotations

import json
import re
from pathlib import Path

from nsgablack.__main__ import _format_doctor_problem_lines, build_parser, main
from nsgablack.project.doctor_core.model import DoctorDiagnostic, DoctorReport


def test_project_doctor_json_output_is_machine_readable(tmp_path: Path, capsys) -> None:
    code = main(["project", "doctor", "--path", str(tmp_path), "--format", "json"])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["project_root"] == str(tmp_path.resolve())
    assert payload["summary"]["errors"] == 0
    assert "diagnostics" in payload
    assert isinstance(payload["diagnostics"], list)


def test_problem_lines_use_structured_positions_and_preserve_unknown(tmp_path: Path) -> None:
    report = DoctorReport(
        project_root=tmp_path,
        diagnostics=(
            DoctorDiagnostic(
                level="error",
                code="x-rule",
                message="bad call detected at foo@L37",
                path=str(tmp_path / "x.py"),
                line=8,
                column=4,
            ),
            DoctorDiagnostic(
                level="warn",
                code="y-rule",
                message="something happened at line 9.",
                path=str(tmp_path / "y.py"),
                line=9,
            ),
            DoctorDiagnostic(
                level="info",
                code="z-rule",
                message="no explicit line hint",
                path=str(tmp_path / "z.py"),
            ),
        ),
    )
    text = _format_doctor_problem_lines(report)
    rows = text.splitlines()
    assert rows[0].endswith(": error x-rule: bad call detected at foo@L37")
    assert rows[1].endswith(": warning y-rule: something happened at line 9.")
    assert rows[2].endswith(": info z-rule: no explicit line hint")
    assert ":8:4: error x-rule:" in rows[0]
    assert ":9: warning y-rule:" in rows[1]
    assert rows[2].startswith(f"{tmp_path / 'z.py'}: info z-rule:")
    assert ":1:1:" not in text


def test_project_doctor_parser_accepts_watch_and_format_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "project",
            "doctor",
            "--path",
            ".",
            "--format",
            "problem",
            "--watch",
            "--watch-interval",
            "0.5",
        ]
    )
    assert args.project_cmd == "doctor"
    assert args.format == "problem"
    assert args.watch is True
    assert abs(float(args.watch_interval) - 0.5) < 1e-9
