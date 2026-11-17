# standard library
from typing import (
    Annotated, 
    Literal, 
    Self,
    _AnnotatedAlias,
)

# third party
import torch
from pydantic import BaseModel, Field
from torch import Tensor


Climate: _AnnotatedAlias = Annotated[
    list[Annotated[int, Field(ge=0, le=4)]], Field(min_length=1)
]
Months: _AnnotatedAlias = Annotated[
    list[Annotated[int, Field(ge=1, le=12)]], Field(min_length=1)
]
Terrain: _AnnotatedAlias = Annotated[
    list[Annotated[int, Field(ge=0, le=3)]], Field(min_length=1)
]
Activity: _AnnotatedAlias = Annotated[
    list[Annotated[int, Field(ge=0, le=4)]], Field(min_length=1)
]


class UserResponse(BaseModel):
    budget: int | float = Field(ge=7000)
    climate: Climate
    months: Months
    urban_or_rural: Literal["urban", "rural"]
    terrain: Terrain
    quiet_or_exciting: Literal["quiet", "exciting"]
    activities: Activity
    folk_legends: bool

    def to_tensor(self: Self) -> Tensor:
        """Convert the validated user response into a model input tensor.
    
        Returns:
            Tensor of shape (1, 30), dtype torch.float32.
    
        Feature layout:
            budget (1)
            climate (5)
            months (12)
            urban_or_rural (1)
            terrain (4)
            quiet_or_exciting (1)
            activities (5)
            folk_legends (1)
        """
    
        features: list[float] = [
            float(self.budget),
    
            # Climate: indices 0–4
            *[
                float(index in self.climate)
                for index in range(5)
            ],
    
            # Months: values 1–12
            *[
                float(month in self.months)
                for month in range(1, 13)
            ],
    
            # Urban = 0, Rural = 1
            float(self.urban_or_rural == "rural"),
    
            # Terrain: indices 0–3
            *[
                float(index in self.terrain)
                for index in range(4)
            ],
    
            # Quiet = 0, Exciting = 1
            float(self.quiet_or_exciting == "exciting"),
    
            # Activities: indices 0–4
            *[
                float(index in self.activities)
                for index in range(5)
            ],
    
            # Folk legends: False = 0, True = 1
            float(self.folk_legends),
        ]
    
        return torch.tensor(
            [features],
            dtype=torch.float32,
        )
