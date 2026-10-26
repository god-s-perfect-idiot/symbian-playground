ifeq (WINS,$(findstring WINS, $(PLATFORM)))
ZDIR=$(EPOCROOT)epoc32/release/$(PLATFORM)/$(CFG)/Z
else
ZDIR=$(EPOCROOT)epoc32/data/z
endif

TARGETDIR=$(ZDIR)/resource/apps
ICONTARGETFILENAME=$(TARGETDIR)/pomodoro_aif.mif
ICONDIR=../gfx

do_nothing :
	@true

MAKMAKE : do_nothing
BLD : do_nothing
CLEAN :
	-rm -f "$(ICONTARGETFILENAME)"
LIB : do_nothing
CLEANLIB : do_nothing

RESOURCE :
	mkdir -p "$(TARGETDIR)"
	mifconv "$(ICONTARGETFILENAME)" /c32 "$(ICONDIR)/pomodoro.svg"

FREEZE : do_nothing
SAVESPACE : do_nothing
RELEASABLES :
	@echo $(ICONTARGETFILENAME)
FINAL : do_nothing
