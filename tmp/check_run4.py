import sqlite3

db = sqlite3.connect('trading_paper.db')

print("=== ORDER EVENTS (RUN 4) ===")
events = db.execute('''
    SELECT id, timestamp, event_type, symbol, payload_json 
    FROM audit_log 
    WHERE event_type IN ('ORDER_SUBMITTED', 'ORDER_FILLED', 'ORDER_NOT_FILLED') 
    ORDER BY timestamp DESC 
    LIMIT 20
''').fetchall()

for row in events:
    print(f"{row[0]:3d} | {row[1][-11:]:11s} | {row[2]:20s} | {str(row[3]):8s}")
    if row[4]:
        import json
        try:
            payload = json.loads(row[4])
            if 'qty' in payload:
                print(f"     └─ qty: {payload['qty']}")
        except:
            pass

print("\n=== TOTAL EVENT COUNTS ===")
event_counts = db.execute('''
    SELECT event_type, COUNT(*) as cnt 
    FROM audit_log 
    GROUP BY event_type 
    ORDER BY cnt DESC
''').fetchall()

for row in event_counts:
    print(f"  {row[0]:30s} : {row[1]:4d}")

db.close()
