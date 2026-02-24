"""
Research: ib_insync fill detection patterns

From ib_insync source code review:

1. Trade object is live-updated by wrapper
2. Trade.fills is a list of Fill objects (namedtuple: contract, execution, commissionReport, time)
3. Trade has event signals:
   - fillEvent(trade, fill) - fired when a partial/full fill occurs
   - filledEvent(trade) - fired when order is fully filled
   - statusEvent(trade) - fired on any status change

4. Key properties for poll-free detection:
   - trade.filled (boolean) - True if order is completely filled
   - trade.fills (list) - all Fill objects for this trade
   - trade.orderStatus.filled (quantity filled in current batch)
   - trade.orderStatus.avgFillPrice (average fill price across all fills)

5. The problem with current polling approach:
   - We're reading trade.orderStatus.avgFillPrice which may be a cached/snapshot value
   - IBKR sends fill updates via wrapper callbacks, not via polling
   - We should wait for fillEvent or filledEvent instead of polling avgFillPrice

6. Correct approach for LSE paper trading (may have delayed fills):
   Option A: Use fillEvent with a timeout
     - Register event handler that sets filled_event flag
     - Wait up to 30 seconds for the event to fire
     - Check flag before exiting submit_order()
   
   Option B: Use filled property with timeout polling
     - Poll trade.filled (boolean) instead of avgFillPrice
     - Lighter-weight polling, should be more responsive
     - Check every 100ms for up to 30 seconds
   
   Option C: Hybrid - register event but also poll as fallback
     - Use event for immediate detection
     - Use polling as timeout backup

RECOMMENDATION: Use Option B (poll Trade.filled boolean)
- Simpler than event registration
- Should work with ib_insync live updates (wrapper pushes updates)
- Same timeout approach but more reliable signal
- Fallback: read Trade.fills list if .filled is still False after timeout
"""
