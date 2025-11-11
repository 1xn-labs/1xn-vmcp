#!/usr/bin/env python3
"""PostgreSQL setup script for vMCP."""

import subprocess
import sys


def start_postgres():
    """Start PostgreSQL Docker container with interactive prompts."""
    print("\n🐘 PostgreSQL Docker Setup")
    print("=" * 40)

    # Get user input with defaults
    user = input("Enter PostgreSQL username [vmcp]: ").strip() or "vmcp"
    password = input("Enter PostgreSQL password [vmcp]: ").strip() or "vmcp"
    database = input("Enter database name [vmcp]: ").strip() or "vmcp"
    port = input("Enter port [5432]: ").strip() or "5432"

    print(f"\n✓ Starting PostgreSQL container...")

    # Build docker command
    cmd = [
        "docker", "run", "-d",
        "--name", "vmcp-postgres",
        "-e", f"POSTGRES_USER={user}",
        "-e", f"POSTGRES_PASSWORD={password}",
        "-e", f"POSTGRES_DB={database}",
        "-p", f"{port}:5432",
        "postgres:15"
    ]

    # Run docker command
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✓ PostgreSQL started on port {port}")
        print(f"\n📝 Add to your .env file:")
        print(f"VMCP_DATABASE_URL=postgresql://{user}:{password}@localhost:{port}/{database}")
        print(f"\n💡 To initialize database, run: vmcp db init")
        return 0
    else:
        print(f"❌ Error: {result.stderr}")
        if "already in use" in result.stderr:
            print("\n💡 Container already exists. Run 'vmcp-postgres-stop' first.")
        return 1


def stop_postgres():
    """Stop and remove PostgreSQL Docker container."""
    print("\n🛑 Stopping PostgreSQL container...")

    result1 = subprocess.run(["docker", "stop", "vmcp-postgres"], capture_output=True, text=True)
    result2 = subprocess.run(["docker", "rm", "vmcp-postgres"], capture_output=True, text=True)

    if result1.returncode == 0 and result2.returncode == 0:
        print("✓ PostgreSQL container stopped and removed")
        return 0
    else:
        print(f"❌ Error stopping container")
        if "No such container" in result1.stderr or "No such container" in result2.stderr:
            print("Container 'vmcp-postgres' not found")
        return 1


def logs_postgres():
    """Show PostgreSQL container logs."""
    print("\n📋 PostgreSQL logs (Ctrl+C to exit)...")
    result = subprocess.run(["docker", "logs", "-f", "vmcp-postgres"])
    return result.returncode


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "stop":
            sys.exit(stop_postgres())
        elif command == "logs":
            sys.exit(logs_postgres())
        else:
            print(f"Unknown command: {command}")
            print("Usage: vmcp-postgres [start|stop|logs]")
            sys.exit(1)
    else:
        # Default to start
        sys.exit(start_postgres())


if __name__ == "__main__":
    main()
