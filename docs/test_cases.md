# Automated case evidence

Generated from the final pytest JUnit results. Fixture models and browsers are not real-world AI tests.

| Test | Expected | Actual | Status | Seconds | Components |
| --- | --- | --- | --- | --- | --- |
| `test_config_roundtrip` | Persist/load settings and reject unknown keys | Assertions met | PASS | 0.031 | Real logic; synthetic inputs |
| `test_bad_config[patch0]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.006 | Real logic; synthetic inputs |
| `test_bad_config[patch1]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_bad_config[patch2]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_bad_config[patch3]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_bad_config[patch4]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_bad_config[patch5]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_bad_config[patch6]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_bad_config[patch7]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_bad_config[patch8]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_bad_config[patch9]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.006 | Real logic; synthetic inputs |
| `test_bad_config[patch10]` | Reject invalid endpoint, range or setting type | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_task[Search for accessible computer interfaces]` | Extract the expected search query | Assertions met | PASS | 0.007 | Real logic; synthetic inputs |
| `test_task[Open my browser and search for accessible computer interfaces]` | Extract the expected search query | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_task[Please look up accessible computer interfaces]` | Extract the expected search query | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_task_rejected[delete my files]` | Reject unsupported or invalid request | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_task_rejected[]` | Reject unsupported or invalid request | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_task_rejected[search for xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx]` | Reject unsupported or invalid request | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_task_rejected[search for cats then buy food]` | Reject unsupported or invalid request | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_task_rejected[search for cats\npassword]` | Reject unsupported or invalid request | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_query_is_inert_encoded_data` | Encode query and reject mismatching result URLs | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_screenshot_mapping` | Resize image and map physical bounds correctly | Assertions met | PASS | 0.326 | Real logic; synthetic inputs |
| `test_tars_parser[Thought: Focus browser\nAction: hotkey(key='ctrl l')-expected0]` | Parse the exact expected typed action | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_tars_parser[Action: hotkey(key='enter')-expected1]` | Parse the exact expected typed action | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_tars_parser[Action: type(content='abc')-expected2]` | Parse the exact expected typed action | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_tars_parser[Action: finished()-expected3]` | Parse the exact expected typed action | Assertions met | PASS | 0.006 | Real logic; synthetic inputs |
| `test_tars_parser[Action: click(start_box='(100, 200)')-expected4]` | Parse the exact expected typed action | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_no_code_execution[__import__('os').system('whoami')]` | Reject executable or malformed action syntax | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_no_code_execution[Action: click(start_box=run())]` | Reject executable or malformed action syntax | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_no_code_execution[Action: finished(); print(1)]` | Reject executable or malformed action syntax | Assertions met | PASS | 0.006 | Real logic; synthetic inputs |
| `test_no_code_execution[Action: hotkey(**evil)]` | Reject executable or malformed action syntax | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_no_code_execution[Action: click(start_box='(1001,0)')]` | Reject executable or malformed action syntax | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_no_code_execution[Action: finished(x=1)]` | Reject executable or malformed action syntax | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_no_code_execution[Action: type(content='a',content='b')]` | Reject executable or malformed action syntax | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_json_parser` | Parse valid JSON and reject extra fields | Assertions met | PASS | 0.007 | Real logic; synthetic inputs |
| `test_invalid_actions[action0]` | Reject unsafe action shape or limits | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_invalid_actions[action1]` | Reject unsafe action shape or limits | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_invalid_actions[action2]` | Reject unsafe action shape or limits | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_invalid_actions[action3]` | Reject unsafe action shape or limits | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_invalid_actions[action4]` | Reject unsafe action shape or limits | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_invalid_actions[action5]` | Reject unsafe action shape or limits | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_invalid_actions[action6]` | Reject unsafe action shape or limits | Assertions met | PASS | 0.003 | Real logic; synthetic inputs |
| `test_invalid_actions[action7]` | Reject unsafe action shape or limits | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_policy_cannot_be_elevated` | Enforce exact stage action | Assertions met | PASS | 0.006 | Real logic; synthetic inputs |
| `test_bounded_timeout_and_cancellation` | Timeout and cancellation raise safe exceptions | Assertions met | PASS | 0.063 | Real logic; synthetic inputs |
| `test_expired_or_cancelled_request_does_not_start` | Do not launch transport work when already cancelled or out of time | Assertions met | PASS | 0.004 | Real logic; synthetic inputs |
| `test_executor_checks_stop_before_input` | No browser interaction after cancellation | Assertions met | PASS | 0.005 | Real logic; synthetic inputs |
| `test_success_observes_after_each_action` | Execute three actions and capture seven observations | Assertions met | PASS | 0.557 | Real controller; fake model/desktop |
| `test_model_cannot_finish_early` | Reject early finish without desktop action | Assertions met | PASS | 0.151 | Real controller; fake model/desktop |
| `test_invalid_reply_retry_is_bounded` | Stop after configured invalid-response retries | Assertions met | PASS | 0.135 | Real controller; fake model/desktop |
| `test_transport_failure_is_not_retried` | Stop after one transport failure without another inference or browser action | Assertions met | PASS | 0.122 | Real controller; fake model/desktop |
| `test_expired_response_never_executes_or_retries` | Discard an action that arrives after the whole-task deadline | Assertions met | PASS | 0.140 | Real controller; fake model/desktop |
| `test_action_limit_counts_waits` | Count waits/captures toward the attempt budget | Assertions met | PASS | 0.913 | Real controller; fake model/desktop |
| `test_health_failure_opens_nothing` | Stop before browser opening when health fails | Assertions met | PASS | 0.006 | Real controller; fake model/desktop |
| `test_cancel_inflight_ignores_late_action` | Discard action returned after Stop | Assertions met | PASS | 0.145 | Real controller; fake model/desktop |
| `test_visual_finish_alone_is_not_success` | Reject finish if native URL mismatches | Assertions met | PASS | 0.551 | Real controller; fake model/desktop |
| `test_browser_missing` | Report error for missing browser | Assertions met | PASS | 0.002 | Real controller; fake model/desktop |
| `test_task_deadline` | Stop when task deadline expires | Assertions met | PASS | 0.007 | Real controller; fake model/desktop |
| `test_real_http_image_contract` | Send real HTTP model/image payload to fake server | Assertions met | PASS | 0.638 | Real HTTP; fake inference |
| `test_http_failure_never_succeeds[302]` | Reject HTTP failure without false success | Assertions met | PASS | 0.524 | Real HTTP; fake inference |
| `test_http_failure_never_succeeds[400]` | Reject HTTP failure without false success | Assertions met | PASS | 0.527 | Real HTTP; fake inference |
| `test_http_failure_never_succeeds[401]` | Reject HTTP failure without false success | Assertions met | PASS | 0.516 | Real HTTP; fake inference |
| `test_http_failure_never_succeeds[422]` | Reject HTTP failure without false success | Assertions met | PASS | 0.853 | Real HTTP; fake inference |
| `test_http_failure_never_succeeds[500]` | Reject HTTP failure without false success | Assertions met | PASS | 0.714 | Real HTTP; fake inference |
| `test_http_failure_never_succeeds[503]` | Reject HTTP failure without false success | Assertions met | PASS | 0.586 | Real HTTP; fake inference |
| `test_wrong_model` | Reject a model absent from the server listing | Assertions met | PASS | 0.794 | Real HTTP; fake inference |
| `test_ui_worker_and_stop` | Stop real Qt worker and restore Start control | Assertions met | PASS | 0.573 | Real Qt/queue; fake task |
| `test_speech_toggle_purges_queue` | Mute disables and purges pending speech | Assertions met | PASS | 0.008 | Real Qt/queue; fake task |
| `test_settings_exposes_task_budget_and_image_controls` | Warn about conflicting budgets and preserve performance settings | Assertions met | PASS | 0.221 | Real Qt/queue; fake task |
