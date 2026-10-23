from functools import lru_cache
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from bender_brain import BrainError
from bender_brain.client import Client
from hardware_api import require_control

brain_lock = threading.RLock()


@lru_cache(maxsize=1)
def get_brain():
    return Client()


class ModelChoice(BaseModel):
    model: str = Field(min_length=1, max_length=200)


class AccountChoice(BaseModel):
    account: str = Field(pattern=r'^[a-f0-9]{16}$')


def build_brain_router():
    router = APIRouter(prefix='/api/brain')

    @router.get('/status')
    def status(brain=Depends(get_brain)):
        return brain.auth.status()

    @router.get('/accounts', dependencies=[Depends(require_control)])
    def accounts(brain=Depends(get_brain)):
        return brain.auth.status(private=True)

    @router.get('/models', dependencies=[Depends(require_control)])
    def models(brain=Depends(get_brain)):
        try:
            with brain_lock:
                return brain.models()
        except BrainError as exc:
            raise HTTPException(503, str(exc)) from exc

    @router.post('/model', dependencies=[Depends(require_control)])
    def model(req: ModelChoice, brain=Depends(get_brain)):
        try:
            with brain_lock:
                brain.choose_model(req.model)
            return brain.auth.status()
        except BrainError as exc:
            raise HTTPException(503, str(exc)) from exc

    @router.post('/account', dependencies=[Depends(require_control)])
    def account(req: AccountChoice, brain=Depends(get_brain)):
        try:
            with brain_lock:
                brain.auth.select_account(req.account)
            return brain.auth.status(private=True)
        except BrainError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post('/logout', dependencies=[Depends(require_control)])
    def logout(brain=Depends(get_brain)):
        with brain_lock:
            revoked = brain.auth.logout()
        return dict(**brain.auth.status(), revoked=revoked)

    return router
