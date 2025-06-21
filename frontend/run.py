import subprocess
import sys


def main():
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.port",
                "8501",
                "--server.address",
                "0.0.0.0",
                "--server.headless",
                "true",
            ]
        )
    except KeyboardInterrupt:
        print("\n애플리케이션이 종료되었습니다.")
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main()
