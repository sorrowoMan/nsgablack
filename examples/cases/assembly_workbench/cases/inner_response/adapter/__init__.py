from nsgablack.adapters import VNSAdapter

def build_adapter():
    return VNSAdapter(name="response_vns", batch_size=1, restart_on_stagnation=False)
