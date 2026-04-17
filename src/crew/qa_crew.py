
def build_change_hints(diff:str)->str:
    hints=[]
    if "+" in diff and "-" in diff:
        hints.append("Behavior modified")
    elif "+" in diff:
        hints.append("New logic added")
    elif "-" in diff:
        hints.append("Logic removed")

    hints.append("Check coherence with existing code")
    hints.append("Check contract compatibility")
    hints.append("Check regression risk")

    return "\n".join(hints)
