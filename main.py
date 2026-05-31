from src.backup import Backuper


def main():
    backuper = Backuper()
    backuper.Run()
    print("Done.")


if __name__ == "__main__":
    main()