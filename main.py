from fastapi import FastAPI

router = FastAPI()

@router.get('/')
def main():
    return "Hello world!"
