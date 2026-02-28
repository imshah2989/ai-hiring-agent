import gradio as gr
from fastapi import FastAPI
from server import app as fastapi_app

# Minimal UI for Hugging Face
with gr.Blocks() as demo:
    gr.Markdown("# 🚀 AI Hiring Agent Backend")
    gr.Markdown("Server Status: **Online**")
    gr.Markdown("Access the API at: [🔗 /docs](/docs)")

# Mount FastAPI app
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
