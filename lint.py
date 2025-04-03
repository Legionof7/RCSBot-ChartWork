#!/usr/bin/env python3
"""
Run linting on the codebase with appropriate configuration.
"""
import subprocess
import sys

def run_black():
    """Run Black formatter."""
    print("Running Black formatter...")
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/black", "model_service.py", "main.py", "test_interventions.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        print(result.stdout)
        if result.stderr:
            print(f"Black errors: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error running Black: {e}")
        return False

def run_flake8():
    """Run Flake8 linter with custom rules."""
    print("\nRunning Flake8 linter...")
    try:
        # Run flake8 but ignore long lines in model_service.py
        model_service_check = subprocess.run(
            [
                "/opt/homebrew/bin/flake8", 
                "model_service.py", 
                "--ignore=E501,E402,W503,W504"
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        
        # Run flake8 on other files with standard rules
        other_files_check = subprocess.run(
            [
                "/opt/homebrew/bin/flake8", 
                "main.py", "test_interventions.py", 
                "--max-line-length=120", 
                "--ignore=E203,W503,E402"
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        
        if model_service_check.stdout:
            print("Issues in model_service.py:")
            print(model_service_check.stdout)
            
        if other_files_check.stdout:
            print("Issues in other files:")
            print(other_files_check.stdout)
            
        if model_service_check.stderr or other_files_check.stderr:
            print("Flake8 errors:")
            if model_service_check.stderr:
                print(model_service_check.stderr)
            if other_files_check.stderr:
                print(other_files_check.stderr)
                
        return model_service_check.returncode == 0 and other_files_check.returncode == 0
    except Exception as e:
        print(f"Error running Flake8: {e}")
        return False

def main():
    """Run all linters."""
    print("RCSBot-ChartWork Linting\n" + "=" * 25)
    black_success = run_black()
    flake8_success = run_flake8()
    
    if black_success and flake8_success:
        print("\n✅ All linting checks passed!")
        return 0
    else:
        print("\n❌ Some linting checks failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())