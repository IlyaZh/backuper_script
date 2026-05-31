from src.backup import Backuper


def main() -> None:
    backuper = Backuper()
    backuper.Run()
    print("Done.")


if __name__ == "__main__":
    main()
