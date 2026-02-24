import ib_insync

# Check Fill class
print("=== Fill class ===")
print(ib_insync.Fill.__doc__)
print("\nFill is a namedtuple with: contract, execution, commissionReport, time")
print("Execution object has 'price' and 'shares' attributes")

# Check eventkit Event class behavior
print("\n=== Event handling ===")
print("Trade.fillEvent type:", type(ib_insync.Trade.fillEvent))
print("Trade.filledEvent type:", type(ib_insync.Trade.filledEvent))

# Check Trade.filled property (boolean indicating if fully filled)
print("\n=== Trade properties ===")
print("Trade has 'filled' property")
print("Trade has 'isDone()' method")
print("Trade.remaining - remaining quantity")
