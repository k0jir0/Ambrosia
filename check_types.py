# Check which types are imported but not actually defined
types_to_check = [
    "BrokerSandboxExecution",
    "BrokerSandboxOrderRequest",
    "BrokerSandboxPosition",
    "AttributionReport",
    "AttributionRequest",
    "FunctionRegistryEntry",
    "MobileAlertEvent",
    "MobileAlertSubscription",
    "MobileAlertSubscriptionCreate",
    "GuardrailPolicyProfile",
    "GuardrailPolicyProfileCreate",
    "GuardrailPolicyActivateRequest",
]

from services.api.app import models
import inspect

available = [name for name, obj in inspect.getmembers(models) if inspect.isclass(obj) and not name.startswith('_')]

print("Undefined types:")
for t in types_to_check:
    if t not in available:
        print(f"  - {t}")
