
PC-Inspector Starting...

Installing dependencies...

[notice] A new release of pip is available: 25.2 -> 25.3
[notice] To update, run: C:\Users\haith\Documents\Vibe Projects\pc-inspector\venv\Scripts\python.exe -m pip install --upgrade pip

========================================
PC-Inspector is starting...
Dashboard: http://localhost:5000
========================================


==================================================
PC-Inspector Started
==================================================
Dashboard: http://localhost:5000
API: http://localhost:5000/api/status
==================================================

 * Serving Flask app 'app'
 * Debug mode: off
2026-01-30 01:33:06,441 - werkzeug - INFO - WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.163:5000
2026-01-30 01:33:06,441 - werkzeug - INFO - Press CTRL+C to quit
2026-01-30 01:33:07,869 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:07] "GET / HTTP/1.1" 304 -
2026-01-30 01:33:07,880 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:07] "GET /style.css HTTP/1.1" 304 -
2026-01-30 01:33:08,093 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:08] "GET /src/main.js HTTP/1.1" 304 -
2026-01-30 01:33:08,422 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:08] "GET /src/pages/issues.js HTTP/1.1" 304 -
2026-01-30 01:33:08,423 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:08] "GET /src/api/client.js HTTP/1.1" 304 -
2026-01-30 01:33:08,423 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:08] "GET /src/pages/dashboard.js HTTP/1.1" 304 -
2026-01-30 01:33:08,424 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:08] "GET /src/pages/hardware.js HTTP/1.1" 304 -
2026-01-30 01:33:08,423 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:08] "GET /src/pages/timeline.js HTTP/1.1" 304 -
2026-01-30 01:33:08,686 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:08] "GET /api/hardware/current HTTP/1.1" 200 -
2026-01-30 01:33:08,733 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:08] "GET /api/issues?limit=5&offset=0 HTTP/1.1" 200 -
2026-01-30 01:33:10,015 - backend.collectors.base - INFO - [HardwareCollector] Starting GPU collection for snapshot 24
2026-01-30 01:33:10,015 - backend.collectors.base - INFO - [HardwareCollector] Connecting to WMI...
2026-01-30 01:33:10,023 - backend.collectors.base - INFO - [HardwareCollector] Querying Win32_VideoController...
2026-01-30 01:33:10,168 - backend.collectors.base - INFO - [HardwareCollector] Found 2 video controller(s)
2026-01-30 01:33:10,177 - backend.collectors.base - INFO - [HardwareCollector] Processing GPU: AMD Radeon(TM) Graphics (Driver: 32.0.13018.6, RAM: -2147483648)
2026-01-30 01:33:10,177 - backend.collectors.base - INFO - [HardwareCollector]   is_nvidia=False, is_amd_discrete=False, is_integrated=True
2026-01-30 01:33:10,177 - backend.collectors.base - INFO - [HardwareCollector]   Setting as backup GPU (integrated)
2026-01-30 01:33:10,186 - backend.collectors.base - INFO - [HardwareCollector] Looking up NVIDIA driver version from registry...
2026-01-30 01:33:10,187 - backend.collectors.base - INFO - [HardwareCollector] Checking registry path: SYSTEM\CurrentControlSet\Services\nvlddmkm
2026-01-30 01:33:10,187 - backend.collectors.base - INFO - [HardwareCollector]   Path not found or error: 'winreg.PyHKEY' object has no attribute 'CloseKey'
2026-01-30 01:33:10,187 - backend.collectors.base - INFO - [HardwareCollector] Checking registry path: SOFTWARE\NVIDIA Corporation\Global\GFXDevice
2026-01-30 01:33:10,187 - backend.collectors.base - INFO - [HardwareCollector]   Path not found or error: [WinError 2] The system cannot find the file specified
2026-01-30 01:33:10,187 - backend.collectors.base - INFO - [HardwareCollector] Checking registry path: SOFTWARE\NVIDIA Corporation\NvCleanInstall
2026-01-30 01:33:10,187 - backend.collectors.base - INFO - [HardwareCollector]   Path not found or error: [WinError 2] The system cannot find the file specified
2026-01-30 01:33:10,187 - backend.collectors.base - INFO - [HardwareCollector] Checking registry path: SYSTEM\CurrentControlSet\Control\Class\{4D36E968-E325-11CE-BFC1-08002BE10318}
2026-01-30 01:33:10,187 - backend.collectors.base - INFO - [HardwareCollector]   Path not found or error: 'winreg.PyHKEY' object has no attribute 'CloseKey'
2026-01-30 01:33:10,187 - backend.collectors.base - INFO - [HardwareCollector] Attempting detailed search in device class registry...
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector]   Checking subkey: 0000
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector]     Found NVIDIA GPU: NVIDIA GeForce RTX 5090
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector]     DriverVersion value: 32.0.15.9174
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector] Got NVIDIA user-facing driver version from registry: 32.0.15.9174
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector] Processing GPU: NVIDIA GeForce RTX 5090 (Driver: 32.0.15.9174, RAM: -1048576)
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector]   is_nvidia=True, is_amd_discrete=False, is_integrated=False
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector]   Setting as preferred GPU (NVIDIA)
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector] Selected GPU: {'name': 'NVIDIA GeForce RTX 5090', 'driver': '32.0.15.9174', 'vram': -1048576, 'is_discrete': True}
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector] VRAM bytes from WMI: -1048576
2026-01-30 01:33:10,188 - backend.collectors.base - INFO - [HardwareCollector] Got VRAM from known database: 32768MB (32GB)
2026-01-30 01:33:10,197 - backend.collectors.base - INFO - [HardwareCollector] NVIDIA devices found: 1
2026-01-30 01:33:10,216 - backend.collectors.base - INFO - [HardwareCollector] GPU Memory: 3214MB used
2026-01-30 01:33:10,216 - backend.collectors.base - INFO - [HardwareCollector] GPU Temperature: 52°C
2026-01-30 01:33:10,217 - backend.collectors.base - INFO - [HardwareCollector] Creating GPU state: name=NVIDIA GeForce RTX 5090, driver=32.0.15.9174, vram_total=32768MB, vram_used=3214MB, temp=52°C
2026-01-30 01:33:10,217 - backend.collectors.base - INFO - [HardwareCollector] Saving GPU state to database...
2026-01-30 01:33:10,219 - backend.collectors.base - INFO - [HardwareCollector] ✅ Recorded GPU: NVIDIA GeForce RTX 5090 (Driver: 32.0.15.9174, VRAM: 32768MB)
2026-01-30 01:33:10,220 - backend.collectors.base - INFO - [HardwareCollector] GPU data collected
2026-01-30 01:33:11,229 - backend.collectors.base - INFO - [HardwareCollector] Recorded CPU: 16 cores @ 4300.0MHz
2026-01-30 01:33:11,229 - backend.collectors.base - INFO - [HardwareCollector] CPU data collected
2026-01-30 01:33:11,232 - backend.collectors.base - INFO - [HardwareCollector] Recorded Memory: 93.6GB total, 30.1% used
2026-01-30 01:33:11,232 - backend.collectors.base - INFO - [HardwareCollector] Memory data collected
2026-01-30 01:33:11,265 - backend.collectors.base - WARNING - [MonitorCollector] PnP monitor query failed (will try alternative method): <x_wmi: Unexpected COM Error (-2147217385, 'OLE error 0x80041017', None, None)>
2026-01-30 01:33:11,353 - backend.collectors.base - INFO - [MonitorCollector] Found 2 monitors via desktop monitor
2026-01-30 01:33:11,357 - backend.collectors.base - INFO - [MonitorCollector] Recorded: Default Monitor (Unknown) - connected
2026-01-30 01:33:11,359 - backend.collectors.base - INFO - [MonitorCollector] Recorded: Generic PnP Monitor (Unknown) - connected
2026-01-30 01:33:11,360 - backend.collectors.base - INFO - [MonitorCollector] Recorded 2 monitor(s)
2026-01-30 01:33:11,360 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:11] "POST /api/collect/all HTTP/1.1" 200 -
2026-01-30 01:33:11,679 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:11] "GET /api/hardware/current HTTP/1.1" 200 -
2026-01-30 01:33:11,930 - werkzeug - INFO - 127.0.0.1 - - [30/Jan/2026 01:33:11] "GET /api/issues?limit=5&offset=0 HTTP/1.1" 200 -