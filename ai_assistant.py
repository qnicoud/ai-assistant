"""
An app to interact with MIstral Codestral assistant served locally with ollama
"""

import requests, json

from textual.app        import App, ComposeResult
from textual.widgets    import Footer, Header, Markdown, Input, Label, Static
from textual.containers import VerticalScroll, Vertical, Horizontal

ollama_url = "http://127.0.0.1:11434/api/generate"

class Prompt(Input):
    BORDER_TITLE = "Prompt"

class Response(Markdown):
    BORDER_TITLE = "Codestral"

class Query(Label):
    BORDER_TITLE = "You"

class AiAssistant(App):
    CSS_PATH    = "styles.tcss"
    AUTO_FOCUS  = "Prompt"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        #Place Header and Footer
        yield Header()
        yield Footer()
        #yield VerticalScroll(Markdown("", id='markdown', classes = "box"))
        yield VerticalScroll(Vertical(id = "log"), classes = "box")

        yield Prompt(
            placeholder = "What would you ask Codestral?",
            type = "text",
            classes = "box prompt",
            id = 'input'
        )

    def submit_query(self, message) -> str:
        data = {
            "model": "codestral",
            "prompt": f"Please format your answer to the following prompt in markdown, without mentionning it in the answer: {message}",
            "stream": False
        }
        response = requests.post(url = ollama_url, json = data)

        if response.status_code == 200:
            result = response.json()
            return f'_{result["created_at"]}_\n\n{result["response"]}'
        else:
            return "Sorry, we couldn't reach the ai..."

    def on_input_submitted(self, message: Input.Submitted) -> None:
        #self.query_one('#markdown').update(message.value)
        #self.answers = f"{self.answers}\n\n{message.value}"
        #self.query_one('#markdown').update(self.answers)
        self.query_one('#input').clear()

        self.query_one('#log').mount(Horizontal(
            Static(classes = "spacer"),
            Query(message.value, shrink = True, classes = "box query")
            ))
        tmp_markdown = Response(self.submit_query(message.value), classes = "box response")
        #tmp_markdown.allow_vertical_scroll = False
        self.query_one('#log').mount(tmp_markdown) 
        #self.query_one('#log').mount(Markdown(self.submit_query(message.value), classes = "box answer"))

if __name__ == "__main__":
    app = AiAssistant()
    app.run()
