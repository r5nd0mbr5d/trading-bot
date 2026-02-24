"""
Key insight: Trade.filled property checks Trade.fills list.
If Trade.fills is empty during polling, the wrapper isn't pushing fill events.

Possible causes:
1. Wrapper callbacks not firing during polling
2. Need to call ib.sleep(0) or event loop processing to handle callbacks
3. Need to use a different API method to query fills

Testing different approaches:

APPROACH 1: Use Trade.fills directly (current attempted)
- Poll trade.filled (which sums trade.fills)
- Issue: trade.fills not being updated by wrapper during polling  
- Why: Callbacks may need event loop processing

APPROACH 2: Use Trade.filled boolean but with waitOnUpdate in loop
- Instead of sleep(1), use self._ib.waitOnUpdate(timeout=1)
- This gives wrapper a chance to process callbacks
- Should be more responsive than time.sleep

APPROACH 3: Query orderStatus with manual refresh
- Use self._ib.requestAllOpenOrders() or requestOpenOrders()
- Explicitly request status update from IBKR
- Then check trade.orderStatus.avgFillPrice

APPROACH 4: Check trade.isDone() 
- trade.isDone() returns True if order is completed (filled or cancelled)
- Use this with polling instead of checking avgFillPrice

RECOMMENDATION FOR IMMEDIATE FIX:
Change polling to use:
  1. self._ib.waitOnUpdate(timeout=1) instead of time.sleep(1) 
     - Gives wrapper chance to process callbacks
  2. Check trade.filled > initial_qty or trade.isDone()
     - More reliable signals than avgFillPrice
  3. Fallback: Check trade.orderStatus.status == 'Filled'
     - Status moves to Filled when all filled
"""
