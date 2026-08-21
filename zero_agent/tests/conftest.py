"""No fixtures — and that is the point.

``tests/conftest.py`` builds a live Postgres schema in a session-scoped autouse
fixture, so every test under ``tests/`` needs a running database. The child-agent
surface deliberately needs nothing but this repository, and its tests have to be
runnable on a laptop that has not started Postgres — otherwise the claim that
ZERO can invoke this agent without the database layer is untested.

Living in its own directory gives this suite its own conftest and keeps that
independence real.
"""
