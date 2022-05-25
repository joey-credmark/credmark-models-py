from credmark.cmf.model import Model
from credmark.cmf.types import ComposeEachInputDto, ComposeEachOutputDto
from credmark.dto import IterableListGenericDTO

@Model.describe(
    slug="compose.each",
    version="1.0",
    display_name="Account Portfolios for a list of Accounts",
    description="All of the token holdings for an account",
    developer="Credmark",
    input=ComposeEachInputDto,
    output=ComposeEachOutputDto)
class ComposeEach(Model):
    def run(self, _:ComposeEachInputDto) -> ComposeEachOutputDto:

        model_outputs = [
            ComposeEachOutputDto.ComposeEachOutputRowDto(
                input=i,
                output=self.context.run_model(_.destination.slug, input=i))
            for i in _.input
            ]

        return ComposeEachOutputDto(
            outputs=model_outputs,
            destination=_.destination)
