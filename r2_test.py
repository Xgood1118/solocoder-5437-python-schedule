"""R2 verify test for SoloCoder 5437-python-schedule.
Re-checks the 5 R1 critical bugs against current code.
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
print('R2 RE-CHECK - SoloCoder 5437-python-schedule')
print('='*60)

# ==========================================================
# BUG 1: holiday_change_replan - 工单不应该被排在节假日
# ==========================================================
print('\n=== BUG 1: holiday_change_replan ===')
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
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  Initial WOs: {len(r["work_orders"])}')
sched_before, _ = get(f'{BASE}/schedule')
for w in sched_before['work_orders']:
    print(f'    {w["order_no"]}: {w["start_time"]} ~ {w["end_time"]}')

# Set 2026-06-15 as holiday
post(f'{BASE}/lines/holidays', {'dates': ['2026-06-15']})
print('  Set 2026-06-15 as holiday')
hr, _ = post(f'{BASE}/replan/holiday-change')
print(f'  Holiday replan: solver={hr["solver_used"]}, WOs={len(hr["work_orders"])}, diffs={len(hr["diffs"])}')
sched_after, _ = get(f'{BASE}/schedule')
holiday_violation = False
for w in sched_after['work_orders']:
    d = w['start_time'][:10]
    if d == '2026-06-15':
        print(f'  FAIL: WO {w["order_no"]} still on 2026-06-15')
        holiday_violation = True
    print(f'    After: {w["order_no"]}: {w["start_time"]} ~ {w["end_time"]}')

if not holiday_violation:
    print('  PASS: No WO on holiday 2026-06-15')
else:
    print('  BUG1 STILL EXISTS')

# ==========================================================
# BUG 2: manual_adjust 应该拒绝周末/节假日
# ==========================================================
print('\n=== BUG 2: manual_adjust weekend/holiday ===')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/orders', {
    'order_no': 'Q001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-31', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-Q'
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')

# Try adjust to Saturday 2026-12-12 08:00
adj, _ = post(f'{BASE}/replan/manual', {
    'order_no': 'Q001', 'new_start_time': '2026-12-12T08:00:00'
})
print(f'  Adjust to Sat: success={adj.get("success")}, msg={adj.get("message")[:80] if adj.get("message") else "n/a"}')
if not adj.get('success') and '周末' in (adj.get('message') or ''):
    print('  PASS: Saturday rejected')
else:
    print('  BUG2 STILL EXISTS')

# Try adjust to holiday
adj2, _ = post(f'{BASE}/replan/manual', {
    'order_no': 'Q001', 'new_start_time': '2026-06-15T08:00:00'
})
print(f'  Adjust to holiday: success={adj2.get("success")}, msg={adj2.get("message")[:80] if adj2.get("message") else "n/a"}')
if not adj2.get('success') and ('节假日' in (adj2.get('message') or '')):
    print('  PASS: Holiday rejected')
else:
    print('  BUG2 STILL EXISTS')

# ==========================================================
# BUG 3: 首单不应扣 setup_minutes 如果产线已装对应模具
# ==========================================================
print('\n=== BUG 3: First-order setup time ===')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/orders', {
    'order_no': 'M001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-31', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-M'
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
for w in r['work_orders']:
    print(f'  {w["order_no"]}: setup={w["setup_minutes"]}min, start={w["start_time"]} ~ end={w["end_time"]}')

if r['work_orders'][0]['setup_minutes'] == 0:
    print('  PASS: Setup is 0 when mold matches')
else:
    print(f'  BUG3 STILL EXISTS: setup={r["work_orders"][0]["setup_minutes"]}min')

# Also test greedy
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/orders', {
    'order_no': 'M001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-31', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-M'
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=false')
for w in r['work_orders']:
    print(f'  Greedy: {w["order_no"]}: setup={w["setup_minutes"]}min, start={w["start_time"]} ~ end={w["end_time"]}')
if r['work_orders'][0]['setup_minutes'] == 0:
    print('  PASS (greedy): Setup is 0 when mold matches')
else:
    print(f'  BUG3 STILL EXISTS (greedy): setup={r["work_orders"][0]["setup_minutes"]}min')

# ==========================================================
# BUG 4: MAX_UTILIZATION 应该和 MAX_ON_TIME 不同
# ==========================================================
print('\n=== BUG 4: MAX_UTILIZATION distinct from MAX_ON_TIME ===')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/orders', {
    'order_no': 'U001', 'product_code': 'P001', 'quantity': 200,
    'due_date': '2027-12-31', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-U1'
})
post(f'{BASE}/orders', {
    'order_no': 'U002', 'product_code': 'P001', 'quantity': 200,
    'due_date': '2027-12-31', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-U2'
})
obj_ontime = urllib.parse.quote('最大化按时交付订单数')
obj_util = urllib.parse.quote('最大化设备利用率')
r_ontime, _ = post(f'{BASE}/schedule/run?objective={obj_ontime}&use_cp_sat=true')
r_util, _ = post(f'{BASE}/schedule/run?objective={obj_util}&use_cp_sat=true')
r_ontime_wos = r_ontime['work_orders']
r_util_wos = r_util['work_orders']
print(f'  MAX_ON_TIME: solver={r_ontime["solver_used"]}, WOs={len(r_ontime_wos)}')
print(f'  MAX_UTILIZATION: solver={r_util["solver_used"]}, WOs={len(r_util_wos)}')
# Check if objectives differ (different start times or different total end)
# Check if objectives differ
def total_work_min(wos):
    total = 0
    for w in wos:
        s = datetime.fromisoformat(w['start_time'])
        e = datetime.fromisoformat(w['end_time'])
        total += int((e - s).total_seconds() / 60)
    return total

t_ontime = total_work_min(r_ontime_wos)
t_util = total_work_min(r_util_wos)
print(f'  Total work min (on_time): {t_ontime}')
print(f'  Total work min (util):    {t_util}')

# Use a different test: check if obj_exprs differ
# On a problem with VIP+P0 orders, both objectives should produce different placements
# We'll do a separate run with priority/quantity differences
print('\n  Now testing with 3 orders, varying due dates...')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 100, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/orders', {
    'order_no': 'X1', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-06-30', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-X1'
})
post(f'{BASE}/orders', {
    'order_no': 'X2', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-31', 'priority': 'P2',
    'customer_importance': '普通客户', 'customer_name': 'Normal-X2'
})
r_ontime2, _ = post(f'{BASE}/schedule/run?objective={obj_ontime}&use_cp_sat=true')
r_util2, _ = post(f'{BASE}/schedule/run?objective={obj_util}&use_cp_sat=true')
print(f'  MAX_ON_TIME: starts={[w["start_time"][:16] for w in r_ontime2["work_orders"]]}')
print(f'  MAX_UTILIZATION: starts={[w["start_time"][:16] for w in r_util2["work_orders"]]}')

# Check if they're different
t_ontime2 = total_work_min(r_ontime2['work_orders'])
t_util2 = total_work_min(r_util2['work_orders'])
print(f'  Total work (on_time): {t_ontime2}, (util): {t_util2}')

# Different test: Compare the placement of X1 (on_time) vs X2 (util should favor more work, even if later)
def get_order_pos(wos, order_no):
    for w in wos:
        if w['order_no'] == order_no:
            return w['start_time'][:16]
    return None

x1_ontime = get_order_pos(r_ontime2['work_orders'], 'X1')
x1_util = get_order_pos(r_util2['work_orders'], 'X1')
x2_ontime = get_order_pos(r_ontime2['work_orders'], 'X2')
x2_util = get_order_pos(r_util2['work_orders'], 'X2')
print(f'  X1 (VIP, P0, due 6-30): ontime={x1_ontime}, util={x1_util}')
print(f'  X2 (P2, due 12-31):     ontime={x2_ontime}, util={x2_util}')

# On MAX_UTILIZATION the order weight is per work_minutes - check if the result differs
# Note: with all 100 capacity and 50 qty, both fit on day 1
# So we need bigger differences
# Check if obj_exprs was correct
import sys
print('\n  Looking at cp_sat_solver.py MAX_UTILIZATION logic...')
with open('C:/Users/白东鑫/work01/SoloCoder/5437-python-schedule/app/modules/schedule/cp_sat_solver.py', 'r', encoding='utf-8') as f:
    src = f.read()
# Find the obj_exprs block for MAX_UTILIZATION
start = src.find('elif objective == ObjectiveType.MAX_UTILIZATION:')
end = src.find('model.Maximize', start)
print(f'  MAX_UTILIZATION block:')
print(src[start:end].strip())

# ==========================================================
# BUG 5: 排不进的工单应该有 warnings
# ==========================================================
print('\n=== BUG 5: Silent dropped orders ===')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/orders', {
    'order_no': 'P999-O1', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-P1'
})
post(f'{BASE}/orders', {
    'order_no': 'P999-O2', 'product_code': 'P999', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-P2'
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  WOs: {len(r["work_orders"])}')
print(f'  warnings: {r.get("warnings", [])}')
print(f'  conflict_details: {r.get("conflict_details", [])}')
has_warning = False
for w in (r.get('warnings') or []):
    if 'P999' in w or '无可适配' in w or '无可' in w:
        has_warning = True
        break
if has_warning:
    print('  PASS: Warning present for unschedulable order')
else:
    # Check conflict_details
    cd = r.get('conflict_details', [])
    if any('P999' in c for c in cd):
        has_warning = True
        print('  PASS: conflict_details has it')
    else:
        print('  BUG5 STILL EXISTS: no warning/conflict for unschedulable order')

# Greedy
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=false')
print(f'  Greedy WOs: {len(r["work_orders"])}')
print(f'  Greedy warnings: {r.get("warnings", [])}')
print(f'  Greedy conflict_details: {r.get("conflict_details", [])}')
has_warning = False
for w in (r.get('warnings') or []):
    if 'P999' in w or '无可适配' in w:
        has_warning = True
        break
cd = r.get('conflict_details', [])
if any('P999' in c for c in cd):
    has_warning = True
if has_warning:
    print('  PASS: Greedy surfaces warning')
else:
    print('  BUG5 STILL EXISTS: Greedy silent')

print('\n' + '='*60)
print('R2 RE-CHECK COMPLETED')
print('='*60)
