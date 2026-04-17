
def inspect_repo_stack():
    return "stack detection placeholder"

def get_official_docs_reference(stack:str):
    docs={
        "python":"https://docs.python.org/3/",
        "java":"https://docs.oracle.com/en/java/",
        "node":"https://nodejs.org/docs/"
    }
    return docs.get(stack,"not mapped")
