"""Deep R1 review test for SoloCoder 5437-python-schedule.
Probes boundary, conflict, scheduling, and integration logic beyond happy path.
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
print('DEEP R1 REVIEW - SoloCoder 5437-python-schedule')
print('='*60)

print('\n=== Setup: Clear existing data ===')
reset()

# Create test lines
print('\n=== Setup: Create lines ===')
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
post(f'{BASE}/lines', {
    'line_id': 'L2', 'line_name': '产线2', 'supported_products': ['P001', 'P002'],
    'daily_capacity': 30, 'mold_status': '待切换', 'current_mold': None,
    'worker_shift': '两班倒', 'efficiency': 1.0
})
post(f'{BASE}/lines', {
    'line_id': 'L3', 'line_name': '产线3', 'supported_products': ['P003'],
    'daily_capacity': 100, 'mold_status': '已装好', 'current_mold': 'M002',
    'worker_shift': '夜班', 'efficiency': 1.0
})

# =================================================================
# TEST A: Empty schedule edge case
# =================================================================
print('\n--- TEST A: Empty schedule (no orders) ---')
r, err = post(f'{BASE}/schedule/run')
print(f'  work_orders: {len(r["work_orders"])}, solver: {r["solver_used"]}')

# =================================================================
# TEST B: Single order basic scheduling
# =================================================================
print('\n--- TEST B: Single order basic ---')
post(f'{BASE}/orders', {
    'order_no': 'A001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-31', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-A'
})
r, err = post(f'{BASE}/schedule/run?objective={urllib.parse.quote("最大化按时交付订单数")}&use_cp_sat=true')
print(f'  Solver: {r["solver_used"]}, WOs: {len(r["work_orders"])}, conflicts: {r["has_conflicts"]}')
for wo in r['work_orders']:
    print(f'    {wo["order_no"]} -> {wo["line_id"]}: {wo["start_time"]} ~ {wo["end_time"]}')

# =================================================================
# TEST C: Many orders - capacity stress test
# =================================================================
print('\n--- TEST C: 5 orders stress test ---')
post(f'{BASE}/orders', {
    'order_no': 'A002', 'product_code': 'P001', 'quantity': 200,
    'due_date': '2026-12-15', 'priority': 'P1',
    'customer_importance': '大客户', 'customer_name': 'BigB'
})
post(f'{BASE}/orders', {
    'order_no': 'A003', 'product_code': 'P001', 'quantity': 150,
    'due_date': '2026-12-10', 'priority': 'P2',
    'customer_importance': '普通客户', 'customer_name': 'NormalC'
})
post(f'{BASE}/orders', {
    'order_no': 'A004', 'product_code': 'P002', 'quantity': 80,
    'due_date': '2026-12-20', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-D'
})
post(f'{BASE}/orders', {
    'order_no': 'A005', 'product_code': 'P003', 'quantity': 500,
    'due_date': '2026-12-05', 'priority': 'P1',
    'customer_importance': '大客户', 'customer_name': 'BigE'
})
r, err = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  Solver: {r["solver_used"]}, WOs: {len(r["work_orders"])}, conflicts: {r["has_conflicts"]}, solve: {r["solve_time_seconds"]}s')
for wo in r['work_orders']:
    print(f'    {wo["order_no"]} -> {wo["line_id"]}: {wo["start_time"][:16]} ~ {wo["end_time"][:16]}, mold: {wo["mold_code"]}, setup: {wo["setup_minutes"]}min')

# =================================================================
# TEST D: Validate "no overlap on same line" hard constraint
# =================================================================
print('\n--- TEST D: Overlap detection in CP-SAT result ---')
by_line = {}
for wo in r['work_orders']:
    by_line.setdefault(wo['line_id'], []).append(wo)
overlap_found = False
for line_id, wos in by_line.items():
    wos.sort(key=lambda w: w['start_time'])
    for i in range(len(wos)-1):
        if wos[i+1]['start_time'] < wos[i]['end_time']:
            print(f'  ❌ OVERLAP on {line_id}: {wos[i]["order_no"]} ends {wos[i]["end_time"]} but {wos[i+1]["order_no"]} starts {wos[i+1]["start_time"]}')
            overlap_found = True
if not overlap_found:
    print('  ✅ No overlaps in CP-SAT result')

# =================================================================
# TEST E: Greedy fallback path
# =================================================================
print('\n--- TEST E: Greedy fallback ---')
r2, err = post(f'{BASE}/schedule/run?use_cp_sat=false')
print(f'  Solver: {r2["solver_used"]}, WOs: {len(r2["work_orders"])}, conflicts: {r2["has_conflicts"]}, solve: {r2["solve_time_seconds"]}s')
for wo in r2['work_orders']:
    print(f'    {wo["order_no"]} -> {wo["line_id"]}: {wo["start_time"][:16]} ~ {wo["end_time"][:16]}, mold: {wo["mold_code"]}, setup: {wo["setup_minutes"]}min')

# Check greedy for overlaps
by_line = {}
for wo in r2['work_orders']:
    by_line.setdefault(wo['line_id'], []).append(wo)
for line_id, wos in by_line.items():
    wos.sort(key=lambda w: w['start_time'])
    for i in range(len(wos)-1):
        if wos[i+1]['start_time'] < wos[i]['end_time']:
            print(f'  ❌ GREEDY OVERLAP on {line_id}: {wos[i]["order_no"]} and {wos[i+1]["order_no"]}')

# =================================================================
# TEST F: Manual adjust with conflict
# =================================================================
print('\n--- TEST F: Manual adjust conflict detection ---')
# Get current schedule
r3, _ = get(f'{BASE}/schedule')
if len(r3['work_orders']) >= 2:
    first = r3['work_orders'][0]
    second = r3['work_orders'][1]
    if first['line_id'] == second['line_id']:
        # Try to move first to overlap with second
        result, err = post(f'{BASE}/replan/manual', {
            'order_no': first['order_no'],
            'new_start_time': second['start_time']
        })
        print(f'  Manual adjust into conflict: success={result.get("success")}, message={result.get("message")[:80] if result.get("message") else "n/a"}')
    else:
        print(f'  Cannot test (orders on different lines)')

# =================================================================
# TEST G: VIP weighting - does MAX_ON_TIME actually weight VIP higher?
# =================================================================
print('\n--- TEST G: VIP weighting effectiveness ---')
# Add a VIP order with same priority as a Normal one, see if VIP gets better placement
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班', 'efficiency': 1.0
})
# Two orders, both P2, same due date, one VIP one Normal
post(f'{BASE}/orders', {
    'order_no': 'V001', 'product_code': 'P001', 'quantity': 100,
    'due_date': '2026-12-10', 'priority': 'P2',
    'customer_importance': 'VIP', 'customer_name': 'VIP-Cust'
})
post(f'{BASE}/orders', {
    'order_no': 'N001', 'product_code': 'P001', 'quantity': 100,
    'due_date': '2026-12-10', 'priority': 'P2',
    'customer_importance': '普通客户', 'customer_name': 'Normal-Cust'
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  WOs: {[(w["order_no"], w["start_time"][:16], w["end_time"][:16]) for w in r["work_orders"]]}')

# =================================================================
# TEST H: Material readiness check
# =================================================================
print('\n--- TEST H: Material shortage handling ---')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班'
})
post(f'{BASE}/orders', {
    'order_no': 'M001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-X',
    'materials': [
        {'material_code': 'MAT001', 'material_name': '钢', 'required_qty': 10, 'stock_qty': 5, 'is_ok': False},
        {'material_code': 'MAT002', 'material_name': '塑料', 'required_qty': 20, 'stock_qty': 30, 'is_ok': True}
    ]
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  Bottleneck analysis:')
for b in r.get('bottleneck_analysis', []):
    print(f'    {b["order_no"]}: {b["reason"][:120]}')

# =================================================================
# TEST I: Order with NO compatible line
# =================================================================
print('\n--- TEST I: No compatible line ---')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班'
})
post(f'{BASE}/orders', {
    'order_no': 'X001', 'product_code': 'P999', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-Z'
})
r, err = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  WOs: {len(r["work_orders"])}, solver: {r["solver_used"]}, conflicts: {r["has_conflicts"]}')

# =================================================================
# TEST J: Freeze / unfreeze behavior
# =================================================================
print('\n--- TEST J: Freeze/Manual adjust on frozen ---')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班'
})
post(f'{BASE}/orders', {
    'order_no': 'F001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-F'
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
# Freeze
fr, _ = post(f'{BASE}/replan/freeze/F001')
print(f'  Freeze: {fr["message"]}')
# Try manual adjust on frozen
adj, _ = post(f'{BASE}/replan/manual', {
    'order_no': 'F001', 'new_start_time': '2026-08-01T08:00:00'
})
print(f'  Adjust frozen: success={adj.get("success")}, message={adj.get("message")}')
# Unfreeze
uf, _ = post(f'{BASE}/replan/unfreeze/F001')
print(f'  Unfreeze: {uf["message"]}')

# =================================================================
# TEST K: Holiday change replan
# =================================================================
print('\n--- TEST K: Holiday change triggers replan ---')
# Set a holiday that overlaps a scheduled job
sched, _ = get(f'{BASE}/schedule')
if sched['work_orders']:
    wo = sched['work_orders'][0]
    hdate = wo['start_time'][:10]
    holidays, _ = get(f'{BASE}/lines/holidays/all')
    new_holidays = [hdate]  # Will replace
    hresp, _ = post(f'{BASE}/lines/holidays', {'dates': new_holidays})
    print(f'  Set holiday {hdate}: {hresp["message"]}')
    r, _ = post(f'{BASE}/replan/holiday-change')
    print(f'  Holiday replan: solver={r["solver_used"]}, WOs={len(r["work_orders"])}, diffs={len(r["diffs"])}')
    # Check no jobs on the holiday
    for w in r['work_orders']:
        d = w['start_time'][:10]
        if d == hdate:
            print(f'  ❌ WO {w["order_no"]} still scheduled on holiday {d}')

# =================================================================
# TEST L: Achievement rate
# =================================================================
print('\n--- TEST L: Achievement rate calculation ---')
# Mark F001 as completed with on-time actual
post(f'{BASE}/orders/F001/start')
post(f'{BASE}/orders/F001/complete')
stats, _ = get(f'{BASE}/stats/achievement')
print(f'  Overall: {stats["overall_rate"]}, by_line: {len(stats["by_line"])}, by_product: {len(stats["by_product"])}')

# =================================================================
# TEST M: Gantt endpoints
# =================================================================
print('\n--- TEST M: Gantt charts ---')
g1, err = get(f'{BASE}/gantt/by-line')
g2, err = get(f'{BASE}/gantt/by-order')
g3, err = get(f'{BASE}/gantt/by-customer')
print(f'  by-line rows: {len(g1["rows"])}, by-order rows: {len(g2["rows"])}, by-customer rows: {len(g3["rows"])}')
print(f'  by-line time range: {g1["time_start"][:16]} ~ {g1["time_end"][:16]}')

# =================================================================
# TEST N: Incremental replan
# =================================================================
print('\n--- TEST N: Incremental replan ---')
post(f'{BASE}/orders', {
    'order_no': 'I001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-20', 'priority': 'P1',
    'customer_importance': '大客户', 'customer_name': 'BigI'
})
r, _ = post(f'{BASE}/replan/incremental', ['I001'])
print(f'  Incremental: solver={r["solver_used"]}, is_incremental={r["is_incremental"]}, diffs={len(r["diffs"])}')

# =================================================================
# TEST O: CP-SAT timeout fallback
# =================================================================
print('\n--- TEST O: CP-SAT timeout fallback (force 30s timeout via big problem) ---')
# Generate many orders to potentially timeout
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001', 'P002', 'P003', 'P004'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班'
})
for i in range(15):
    post(f'{BASE}/orders', {
        'order_no': f'BIG{i:03d}', 'product_code': f'P00{(i % 4) + 1}',
        'quantity': 200, 'due_date': '2026-12-15', 'priority': 'P1',
        'customer_importance': '大客户', 'customer_name': f'Cust{i}'
    })
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  WOs: {len(r["work_orders"])}, solver: {r["solver_used"]}, time: {r["solve_time_seconds"]}s')

# =================================================================
# TEST P: Gantt timestamp issues - check time_start vs time_end
# =================================================================
print('\n--- TEST P: Gantt timestamp edge case ---')
g, _ = get(f'{BASE}/gantt/by-line')
if g['rows'] and any(r['bars'] for r in g['rows']):
    for row in g['rows'][:1]:
        for bar in row['bars'][:3]:
            print(f'  Bar {bar["id"]}: {bar["start"]} -> {bar["end"]}, color: {bar["color"]}')

# =================================================================
# TEST Q: Check if manual adjust to non-existent time zone weirdness
# =================================================================
print('\n--- TEST Q: Manual adjust to weekend/holiday time ---')
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班'
})
post(f'{BASE}/orders', {
    'order_no': 'Q001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-Q'
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
# Try to adjust to Saturday 8am (should ideally reject or warn)
adj, _ = post(f'{BASE}/replan/manual', {
    'order_no': 'Q001', 'new_start_time': '2026-12-12T08:00:00'  # Saturday
})
print(f'  Adjust to Saturday: success={adj.get("success")}, msg={adj.get("message")[:80] if adj.get("message") else "n/a"}')
sched, _ = get(f'{BASE}/schedule')
for w in sched['work_orders']:
    if w['order_no'] == 'Q001':
        d = datetime.fromisoformat(w['start_time'])
        print(f'  New start: {w["start_time"]} (weekday={d.weekday()})')
        if d.weekday() >= 5:
            print(f'  ❌ Schedule was placed on weekend without rejection')

# =================================================================
# TEST R: Setup time ignored vs applied
# =================================================================
print('\n--- TEST R: Mold setup time applied correctly ---')
# Schedule two consecutive jobs on same line with different molds
reset()
post(f'{BASE}/lines', {
    'line_id': 'L1', 'line_name': '产线1', 'supported_products': ['P001', 'P002', 'P003'],
    'daily_capacity': 50, 'mold_status': '已装好', 'current_mold': 'M001',
    'worker_shift': '白班'
})
post(f'{BASE}/orders', {
    'order_no': 'S001', 'product_code': 'P001', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-S1'
})
post(f'{BASE}/orders', {
    'order_no': 'S002', 'product_code': 'P002', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-S2'
})
post(f'{BASE}/orders', {
    'order_no': 'S003', 'product_code': 'P003', 'quantity': 50,
    'due_date': '2026-12-15', 'priority': 'P0',
    'customer_importance': 'VIP', 'customer_name': 'VIP-S3'
})
r, _ = post(f'{BASE}/schedule/run?use_cp_sat=true')
print(f'  WOs:')
for w in sorted(r['work_orders'], key=lambda x: x['start_time']):
    print(f'    {w["order_no"]} mold={w["mold_code"]} setup={w["setup_minutes"]}min: {w["start_time"][:16]} ~ {w["end_time"][:16]}')

print('\n' + '='*60)
print('ALL DEEP TESTS COMPLETED')
print('='*60)
