from argparse import ArgumentParser

import uvicorn


def parse_args():
    parser = ArgumentParser(description="Servidor webhook do QAgent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()

