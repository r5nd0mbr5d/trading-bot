import sqlite3

db = sqlite3.connect('trading_paper.db')
cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = cursor.fetchall()
print('Tables in trading_paper.db:')
for table in tables:
    print(f'  - {table[0]}')

# Check audit_event table
print('\nRecent audit events (last 15):')
events = db.execute('''
    SELECT id, event_type, symbol, qty, details, created_at 
    FROM audit_events 
    ORDER BY created_at DESC 
    LIMIT 15
''').fetchall()

for row in events:
    print(f'  {row[0]:3d} | {row[1]:20s} | {str(row[2]):8s} | {str(row[3]):5s} | {row[5][:19]}')
    if row[4]:
        try:
            import json
            details = json.loads(row[4])
            for key, val in list(details.items())[:3]:
                print(f'       └─ {key}: {val}')
        except:
            print(f'       └─ {row[4][:80]}')

db.close()
