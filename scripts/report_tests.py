"""Produce a per-case evidence table from pytest's JUnit output."""
from pathlib import Path
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[1]
report=ET.parse(root/'tmp/test-results.xml')
expectations={
    'test_config_roundtrip':'Persist/load settings and reject unknown keys',
    'test_bad_config':'Reject invalid endpoint, range or setting type',
    'test_task':'Extract the expected search query',
    'test_task_rejected':'Reject unsupported or invalid request',
    'test_query_is_inert_encoded_data':'Encode query and reject mismatching result URLs',
    'test_screenshot_mapping':'Resize image and map physical bounds correctly',
    'test_tars_parser':'Parse the exact expected typed action',
    'test_no_code_execution':'Reject executable or malformed action syntax',
    'test_json_parser':'Parse valid JSON and reject extra fields',
    'test_invalid_actions':'Reject unsafe action shape or limits',
    'test_policy_cannot_be_elevated':'Enforce exact stage action',
    'test_bounded_timeout_and_cancellation':'Timeout and cancellation raise safe exceptions',
    'test_executor_checks_stop_before_input':'No browser interaction after cancellation',
    'test_success_observes_after_each_action':'Execute three actions and capture seven observations',
    'test_model_cannot_finish_early':'Reject early finish without desktop action',
    'test_invalid_reply_retry_is_bounded':'Stop after configured invalid-response retries',
    'test_action_limit_counts_waits':'Count waits/captures toward the attempt budget',
    'test_health_failure_opens_nothing':'Stop before browser opening when health fails',
    'test_cancel_inflight_ignores_late_action':'Discard action returned after Stop',
    'test_visual_finish_alone_is_not_success':'Reject finish if native URL mismatches',
    'test_browser_missing':'Report error for missing browser',
    'test_task_deadline':'Stop when task deadline expires',
    'test_real_http_image_contract':'Send real HTTP model/image payload to fake server',
    'test_http_failure_never_succeeds':'Reject HTTP failure without false success',
    'test_wrong_model':'Reject a model absent from the server listing',
    'test_ui_worker_and_stop':'Stop real Qt worker and restore Start control',
    'test_speech_toggle_purges_queue':'Mute disables and purges pending speech',
    'test_transport_failure_is_not_retried':'Stop after one transport failure without another inference or browser action',
    'test_expired_response_never_executes_or_retries':'Discard an action that arrives after the whole-task deadline',
    'test_expired_or_cancelled_request_does_not_start':'Do not launch transport work when already cancelled or out of time',
    'test_settings_exposes_task_budget_and_image_controls':'Warn about conflicting budgets and preserve performance settings',
}
lines=['# Automated case evidence','',
       'Generated from the final pytest JUnit results. Fixture models and browsers are not real-world AI tests.', '',
       '| Test | Expected | Actual | Status | Seconds | Components |',
       '| --- | --- | --- | --- | --- | --- |']
for case in report.findall('.//testcase'):
    name=case.attrib['name']; base=name.split('[')[0]
    failure=case.find('failure')
    status='PASS' if failure is None and case.find('error') is None else 'FAIL'
    family=case.attrib['classname']
    mode=('Real HTTP; fake inference' if 'transport' in family else
          'Real Qt/queue; fake task' if 'ui' in family else
          'Real controller; fake model/desktop' if 'pipeline' in family else
          'Real logic; synthetic inputs')
    lines.append(f"| `{name.replace('|','/').replace(chr(10),' ')}` | {expectations[base]} | {'Assertions met' if status=='PASS' else 'See JUnit failure'} | {status} | {case.attrib.get('time','')} | {mode} |")
(root/'docs/test_cases.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Recorded',len(report.findall('.//testcase')),'test cases')
