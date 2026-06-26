# COBOL-Translator
I set up a template based on `task.md`. The structure is not exactly the same because the instruction is inconsistent All Python files are currently empty placeholders. Feel free to change the folder structure however you like.

---

## How to Run It

### 1. Install Docker

Download and install **Docker Desktop** (Windows or Mac). You don't need to install Python or COBOL on your actual computer.

### 2. Write Your Code

Add your logic to the python files.

### 3. Update the Script

Open `run.sh` and add your execution command under `# Put your command here`. 
*Example:* `python3 src/parser.py`

### 4. Test Your Code

Run these two commands in your terminal:

```bash
docker build -t cobol-translator .

docker run --rm -v "$(pwd)":/app cobol-translator
```