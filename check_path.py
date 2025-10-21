import os

print("Current file directory:", os.path.dirname(os.path.abspath(__file__)))
print("Current working directory:", os.getcwd())

excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.xlsx")
print("Looking for Excel file at:", excel_path)
print("File exists:", os.path.exists(excel_path))
print("Files in backend folder:", os.listdir(os.path.dirname(os.path.abspath(__file__))))


