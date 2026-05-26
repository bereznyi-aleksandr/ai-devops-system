# BEM-866 processor error classification
Status: JSON_ERROR

Log prefix:
Traceback (most recent call last):
  File "/home/runner/work/ai-devops-system/ai-devops-system/scripts/process_workflow_dispatch_queue.py", line 55, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "/home/runner/work/ai-devops-system/ai-devops-system/scripts/process_workflow_dispatch_queue.py", line 34, in main
    data = json.loads(item.read_text(encoding="utf-8"))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/json/decoder.py", line 353, in raw_decode
    obj, end = self.scan_once(s, idx)
               ^^^^^^^^^^^^^^^^^^^^^^
json.decoder.JSONDecodeError: Invalid control character at: line 1 column 48 (char 47)

