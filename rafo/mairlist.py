class MAirListExport:
    pass

    def __init__(self, id: int):
        self.id = id

    async def run(self):
        yield "STARTING MAIRLIST EXPORT"
        yield "MAIRLIST EXPORT COMPLETED"