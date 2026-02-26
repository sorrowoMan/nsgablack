# GPU + Ray + MySQL Integrated Demo

Demo file: `examples/gpu_ray_mysql_stack_demo.py`

## What it wires
- `GpuEvaluationTemplatePlugin`: optional GPU short-circuit for `evaluate_population`
- Ray distributed evaluator path (`attach_ray_parallel`)
- `MySQLRunLoggerPlugin`: writes run metadata to MySQL on solver finish

## Run examples

CPU fallback only (no ray/mysql):
```powershell
python examples/gpu_ray_mysql_stack_demo.py
```

Enable Ray:
```powershell
python examples/gpu_ray_mysql_stack_demo.py --enable-ray --max-workers 8
```

Enable Ray + MySQL:
```powershell
$env:NSGABLACK_MYSQL_HOST = "127.0.0.1"
$env:NSGABLACK_MYSQL_PORT = "3306"
$env:NSGABLACK_MYSQL_USER = "root"
$env:NSGABLACK_MYSQL_PASSWORD = "your-password"
$env:NSGABLACK_MYSQL_DB = "nsgablack"
$env:NSGABLACK_MYSQL_TABLE = "nsgablack_runs"
python examples/gpu_ray_mysql_stack_demo.py --enable-ray --enable-mysql
```

Force torch backend:
```powershell
python examples/gpu_ray_mysql_stack_demo.py --gpu-backend torch --gpu-device cuda:0
```

## Notes
- If GPU backend or problem GPU hook is unavailable, GPU plugin returns `None` and solver keeps default evaluation path.
- Ray is optional; when `--enable-ray` is off, demo uses thread backend by default.
- If `--enable-ray` is on, ensure `ray` and `cloudpickle` are installed.
- MySQL plugin requires `mysql-connector-python` or `pymysql`.
