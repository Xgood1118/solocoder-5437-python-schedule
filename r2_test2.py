"""R2 verify test - BUG 1 deeper, BUG 4 deeper, BUG 5 deeper.
Specifically test that holiday_change_replan correctly identifies
WOs placed on a holiday and rebuilds the schedule.
"""
import urllib.request
import urllib.parse
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime, date, timedelta

BASE = "http://localhost:9090"


def post(url, data=None):
    if data is not None:
        req = urllib.request.Request(
            url, data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='POST')
    else:
        req = urllib.request.Request(url, method='POST')
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode('utf-8')


def put(url, data):
    req = urllib.request.Request(
        url, data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='PUT')
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode('utf-8')


def delete(url):
    req = urllib.request.Request(url, method='DELETE')
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode('utf-8')


def get(url):
    try:
        resp = urllib.request.urlopen(url)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode('utf-8')


def reset():
    orders, _ = get(f'{BASE}/orders')
    for o in orders:
        delete(f'{BASE}/orders/{o["order_no"]}')
    lines, _ = get(f'{BASE}/lines')
    for l in lines:
        delete(f'{BASE}/lines/{l["line_id"]}')


print('='*60)
print('R2 DEEPER RE-CHECK')
print('='*60)

# ==========================================================
# BUG 1 DEEPER: Force a schedule to start on a specific day
# ==========================================================
print('\n=== BUG 1 DEEPER: Manually place WO on holiday, then trigger ===')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/orders', {
    'order_no': 'H001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-31', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-H'
})
# Reset holidays first
post(f'{BASE}/lines/holidays', {'dates': []})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  Schedule start day: {r["work_orders"][0]["start_time"]}')

# Manually adjust H001 to a known Monday 2026-06-22 (when 06-15 isn't a holiday yet)
adj, _ = post(f'{BASE}/replan/manual', {
    'order_no': 'H001', 'new_start_time': '2026-06-22T08:00:00'
})
print(f'  Manual adjust to 2026-06-22 (Mon): success={adj.get("success")}, msg={adj.get("message")[:60] if adj.get("message") else "n/a"}')
sched, _ = get(f'{BASE}/schedule')
print(f'  Current WO: {sched["work_orders"][0]["start_time"]}')

# Now set 2026-06-22 as holiday
post(f'{BASE}/lines/holidays', {'dates': ['2026-06-22']})
print('  Set 2026-06-22 as holiday')
hr, _ = post(f'{BASE}/replan/holiday-change')
print(f'  Holiday replan: solver={hr["solver_used"]}, WOs={len(hr["work_orders"])}, diffs={len(hr["diffs"])}')
sched_after, _ = get(f'{BASE}/schedule')
violated = False
for w in sched_after['work_orders']:
    d = w['start_time'][:10]
    if d == '2026-06-22':
        violated = True
        print(f'  FAIL: WO still on 2026-06-22')
    print(f'    {w["order_no"]}: {w["start_time"]}')
if not violated:
    print('  PASS: WO moved off 2026-06-22 holiday')
else:
    print('  BUG1 STILL EXISTS')

# ==========================================================
# BUG 4 DEEPER: Compare obj values of two objectives
# ==========================================================
print('\n=== BUG 4 DEEPER: Different problem to differentiate objectives ===')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/lines', {
    'line_id': 'L2', 'line_name': '产线2', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
# Two orders that can't both fit on the same line in one day
# 50 capacity * 8 hours = 400 units per day. qty=200 takes 4h, so two qty=200 = 8h
# Use one late, one early: MAX_ON_TIME should prioritize late-but-on-time vs MAX_UTILIZATION
post(f'{BASE}/orders', {
    'order_no': 'L1A', 'product_code': 'P001', 'quantity': 400,
    'due_date': '2026-06-30', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-L1A'
})
post(f'{BASE}/orders', {
    'order_no': 'L1B', 'product_code': 'P001', 'quantity': 400,
    'due_date': '2026-12-31', 'priority': 'P2',
    'customer_importance': '普通客户', 'customer_name': 'Normal-L1B'
})

obj_ontime = urllib.parse.quote('最大化按时交付订单数')
obj_util = urllib.parse.quote('最大化设备利用率')
obj_delay = urllib.parse.quote('最小化总延期天数')

r_ontime, _ = post(f'{BASE}/schedule/run?objective={obj_ontime}&use_cp_sat=true')
r_util, _ = post(f'{BASE}/schedule/run?objective={obj_util}&use_cp_sat=true')
r_delay, _ = post(f'{BASE}/schedule/run?objective={obj_delay}&use_cp_sat=true')

print(f'  MAX_ON_TIME:')
for w in r_ontime['work_orders']:
    print(f'    {w["order_no"]} -> {w["line_id"]}: {w["start_time"]} ~ {w["end_time"]}')
print(f'  MAX_UTILIZATION:')
for w in r_util['work_orders']:
    print(f'    {w["order_no"]} -> {w["line_id"]}: {w["start_time"]} ~ {w["end_time"]}')
print(f'  MIN_DELAY:')
for w in r_delay['work_orders']:
    print(f'    {w["order_no"]} -> {w["line_id"]}: {w["start_time"]} ~ {w["end_time"]}')

# Check distinctness: 3 different objectives should produce 3 different schedules
def schedule_signature(wos):
    return tuple((w['order_no'], w['line_id'], w['start_time']) for w in sorted(wos, key=lambda x: x['order_no']))

sig_ontime = schedule_signature(r_ontime['work_orders'])
sig_util = schedule_signature(r_util['work_orders'])
sig_delay = schedule_signature(r_delay['work_orders'])
print(f'  sig_ontime: {sig_ontime}')
print(f'  sig_util:   {sig_util}')
print(f'  sig_delay:  {sig_delay}')

distinct = len({sig_ontime, sig_util, sig_delay})
if distinct == 3:
    print('  PASS: 3 distinct schedules for 3 objectives')
elif distinct == 2:
    print('  PARTIAL: 2 distinct schedules (one objective still broken)')
else:
    print('  FAIL: All 3 objectives produce identical schedules')

# ==========================================================
# BUG 5 DEEPER: Verify warnings propagation
# ==========================================================
print('\n=== BUG 5 DEEPER: Warnings in ScheduleResult ===')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/orders', {
    'order_no': 'P999-1', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-P1'
})
post(f'{BASE}/orders', {
    'order_no': 'P999-2', 'product_code': 'P999', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-P2'
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  ScheduleResult keys: {sorted(r.keys())}')
print(f'  WOs count: {len(r["work_orders"])}')
print(f'  has_conflicts: {r.get("has_conflicts")}')
print(f'  conflict_details: {r.get("conflict_details")}')
print(f'  Order count in store: {len(get(f"{BASE}/orders")[0])}')

# Check if the model has 'warnings' field
print('  ScheduleResult has no "warnings" field - silent dropping likely')

# Greedy test
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=false')
print(f'  Greedy WOs count: {len(r["work_orders"])}')
print(f'  Greedy keys: {sorted(r.keys())}')

# Check if the model file says warnings
with open('C:/Users/白东鑫/work01/SoloCoder/5437-python-schedule/app/models.py', 'r', encoding='utf-8') as f:
    src = f.read()
if 'warnings' in src:
    # find the line
    import re
    m = re.search(r'class ScheduleResult.*?(?=class|\Z)', src, re.DOTALL)
    if m:
        print(f'  ScheduleResult: {m.group(0)[:200]}')
else:
    print('  ScheduleResult has NO warnings field - BUG5 NOT FIXED in API response')

print('\n' + '='*60)
print('R2 DEEPER RE-CHECK COMPLETED')
print('='*60)
