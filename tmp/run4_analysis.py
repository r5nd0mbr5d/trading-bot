import sqlite3

db = sqlite3.connect('trading_paper.db')

# Count events
signals = db.execute('SELECT COUNT(*) FROM audit_log WHERE event_type="SIGNAL"').fetchone()[0]
dq_blocks = db.execute('SELECT COUNT(*) FROM audit_log WHERE event_type="DATA_QUALITY_BLOCK"').fetchone()[0]
ks_triggered = db.execute('SELECT COUNT(*) FROM audit_log WHERE event_type="KILL_SWITCH_TRIGGERED"').fetchone()[0]
submissions = db.execute('SELECT COUNT(*) FROM audit_log WHERE event_type="ORDER_SUBMITTED"').fetchone()[0]
fills = db.execute('SELECT COUNT(*) FROM audit_log WHERE event_type="ORDER_FILLED"').fetchone()[0]
not_filled = db.execute('SELECT COUNT(*) FROM audit_log WHERE event_type="ORDER_NOT_FILLED"').fetchone()[0]

print("=== RUN 4 SIGNAL FLOW ANALYSIS ===")
print(f"Signals generated: {signals}")
print(f"  ├─ Data quality blocks: {dq_blocks}")
print(f"  ├─ Kill-switch triggers: {ks_triggered}")
print(f"  └─ Orders submitted: {submissions}")
print(f"      ├─ Fills detected: {fills}")
print(f"      └─ Not filled: {not_filled}")
print(f"\nAcceptance criteria: filled_order_count >= 5")
print(f"Result: {fills} fills {'✅ PASS' if fills >= 5 else '❌ FAIL'}")

print("\n=== KEY INSIGHT ===")
print(f"Signals to orders: {signals} → {submissions} ({submissions}/{signals} submitted)")
print(f"Order outcome: {submissions} orders → {fills} fills ({fills}/{submissions} filled)")
print(f"\nProblem: Orders ARE being submitted (7/13 signals), but polling is NOT capturing fills")
print(f"Root cause: avgFillPrice polling is still returning 0 during 30-second window")

db.close()
