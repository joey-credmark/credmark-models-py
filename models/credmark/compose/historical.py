from credmark.cmf.model import Model
from credmark.cmf.types import ComposeHistoricalInputDto

@Model.describe(
    slug="compose.historical",
    version="1.0",
    display_name="Compose Historical",
    description="Run a Model Historically",
    developer="Credmark",
    input=ComposeHistoricalInputDto,
    output=dict)
class ComposeHistorical(Model):
    def run(self, _:ComposeHistoricalInputDto):
        return self.context.historical.run_model_historical(
            model_slug=_.destination.slug,
            model_input=_.input,
            window=_.window,
            interval=_.interval)
