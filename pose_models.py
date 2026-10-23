"""Bounded, code-free shapes shared by the editors and face websocket."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Pixel = Annotated[float, Field(ge=0, le=80, allow_inf_nan=False)]
Fraction = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class MouthShape(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['mouth']
    top: list[Pixel] = Field(min_length=121, max_length=121)
    bottom: list[Pixel] = Field(min_length=121, max_length=121)
    rounded: bool = False
    cutoff: Pixel = 80
    teeth: int = Field(default=5, ge=0, le=10)
    thickness: int = Field(default=1, ge=1, le=3)

    @model_validator(mode='after')
    def ordered_lips(self):
        if any(top > bottom for top, bottom in zip(self.top, self.bottom)):
            raise ValueError('La ligne du haut doit rester au-dessus de la ligne du bas.')
        return self


class Eye(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cx: float = Field(ge=80, le=720, allow_inf_nan=False)
    cy: float = Field(ge=80, le=400, allow_inf_nan=False)
    rx: float = Field(ge=25, le=200, allow_inf_nan=False)
    ry: float = Field(ge=25, le=170, allow_inf_nan=False)
    pupil_x: float = Field(default=0, ge=-200, le=200, allow_inf_nan=False)
    pupil_y: float = Field(default=0, ge=-170, le=170, allow_inf_nan=False)
    pupil_size: float = Field(default=34, ge=8, le=80, allow_inf_nan=False)
    top: list[Fraction] = Field(min_length=3, max_length=3)
    bottom: list[Fraction] = Field(min_length=3, max_length=3)

    @model_validator(mode='after')
    def ordered_lids(self):
        if any(a > b for a, b in zip(self.top, self.bottom)):
            raise ValueError('Les paupières ne doivent pas se croiser.')
        return self


class EyesShape(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['eyes']
    eyes: list[Eye] = Field(min_length=2, max_length=2)
    color: str = Field(default='#f8f2c6', pattern=r'^#[0-9a-fA-F]{6}$')


Shape = Annotated[MouthShape | EyesShape, Field(discriminator='kind')]


class PoseSave(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    definition: Shape
    revision: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def nonempty_name(self):
        self.name = self.name.strip()
        if not self.name: raise ValueError('Un nom est requis.')
        return self
