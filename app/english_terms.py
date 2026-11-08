"""Offline recognition vocabulary, never a replacement translation dictionary.

Keep shared/ambiguous words separate: they cannot establish English on their own.
The short-message fallback requires every token to be known and an English cue.
"""

ENGLISH_WORDS = frozenset("""+about above actually afraid after again against ago agree ahead almost alone
already alright also always amazing angry annoyed another answer anything anyway
anywhere apologize appreciate around ask asked asking asleep awesome awkward
away babe babes baby back bad barely bathroom beach beautiful beauty because
bed bedroom been before believe belong below better between big birthday black
blond blonde blue blush blushing bored boring both boyfriend break bring broken
bro brother btw busy buy buying bye call called calling came can't cannot care
careful catch change changed changing cheap check checked checking cheer cheers
chill chilling chillin clothes clothing cold collar color colour come comes
coming comfy confused cool could couldn't couple couples crazy cuddle cuddles
cuddling cute cutie cuties dance danced dances dancing darling date dating dear
definitely did didn't different do does doesn't doing done don't down dream
dreams dress dressed drink drinking dude each early easy either else enough
enjoy enjoyed enjoying even evening ever every everybody everyone everything
everywhere exactly excited excuse expensive eyes face fair family far favorite
favourite feel feeling feels female few fine finished first fit fits fix fixed
flirt flirting follow following forgot found free friend friends friendly
friendship from fun funny gave get gets getting girl girlfriend girls give
giving glad go goes going gonna gone good gorgeous got gotta great green grey
gray guess guy guys hair handsome hang hanging happen happened happens happy
hard has hasn't have haven't having he he'd he'll he's head hear heard heart
hearts hello help helped helping her here here's hers herself hey hi hide him
himself his hold holding home hope hoping horny hot hotter hottest house how
however hug hugs hugging hungry husband hurt i i'd i'll i'm i've idea if ignore
ignored ill important interested invite invited inviting is isn't it it's its
itself jealous join joined joining joke joking just keep kinda kiss kisses
kissing knew know knowing knows late lately later laugh laughing leave leaving
left less let let's life light like liked likes liking little live lived lives
living lonely long look looked looking looks lost lot lots love loved lovely
lover lovers loves loving low luck lucky made make makes making male man many
married marry matter may maybe mean means meant meet meeting men message
messages might mind mine miss missed misses missing moment money mood more
most mouth move moved moving much must my myself naked naughty near nearly
need needed needing needs never new next nice night nobody nope nothing now
number of off often old once one only open other others our ours ourselves
out outfit outfits outside over own partner people perfect perhaps person
phone picture pictures pink place play played playing please pleasure point
pose poses posing pretty probably profile proud put question quick quiet
quite rather read ready real really reason red relax relaxed relaxing remember
reply replied right room sad said same saw say saying says scared screen
second see seeing seems seen self send sending sent serious seriously set
several sexy shall share she she'd she'll she's shirt shoes shop shopping
short should shouldn't show shy sick side since single sit sitting skin skirt
sleep sleeping sleepy slow small smile smiles smiling so somebody someone
something sometimes somewhere soon sorry sound sounds speak speaking special
spend stand standing start stay still stop stopped story stuck stuff such
sure sweet sweetheart sweetie swimsuit take taking talk talked talking tall
tell telling than thank thanks that that's their theirs them themselves then
there there's these they they'd they'll they're they've thing things think
thinking thirsty this those though thought through tired today together told
tomorrow tonight too took totally touch tp ty tysm understand understood until
up update upset us use used using usually very voice wait waited waiting wake
walk walking wanna want wanted wants warm was wasn't watch watching way we
we'd we'll we're we've wear wearing weekend welcome well went were weren't
what what's whatever when where where's whether which while white who who's
why wife will wish with without won't wonder wonderful work worked working
world worried worse worst would wouldn't wrong year years yellow yep yes
yesterday yet you you'd you'll you're you've young your yours yourself
afk asap brb bbl bbs bf bff cuz cos coz dunno ffs fyi gf gg gimme gonna gotta
gr8 gtg gotta hbu hru idc idk ikr imo imho irl jk l8r lemme lmk np nvm ofc
omg omw pls plz rn rly sry thx tho tbh tmr tmrw ttyl wbu wdym wyd wtf yw
aint ain't arent dont doesnt didnt cant couldnt shouldnt wouldnt wont wasnt
werent havent hasnt hadnt wheres whats whos thats youre youve youll im ive
teleport teleporting teleported landmark landmarks rez rezzing rezzed mesh
meshbody applier hud huds lag laggy lagging crashed crashing crash viewer
viewers inventory notecard notecards sim sims region parcel parcels prim prims
rezz rigged rigging unrigged attach attached attachment attachments detach
detached unpack unpacking unpacked unpacker demo demos vendor vendors purchase
buy bought paid pay payment rent rented renting rental rentals store stores
landowner owner permissions permission copy modify transfer animation animations
animated animate avatar avatars avi avies avs ao poseball poseballs furniture
furnished texture textures script scripts scripted sandbox freebies freebie
gift gifts group groups club clubs party parties event events dj dancefloor
stream streaming mic microphone headphones mute muted unmute cam camera
zoom windlight eep alpha alphas omega bakes baked bom layers layer head heads
body bodies shape shapes eyes eyebrow eyebrows eyelash eyelashes tattoo tattoos
piercing piercings freckles nails makeup lipstick feet foot hands hand neck
chest boobs breasts butt ass dick cock pussy sex sexual fuck fucking fucked
damn shit bitch bastard bullshit hell nsfw cuddleball cuddlebuddy roleplay
roleplaying roleplayer rp cuddlebuddy cuddleball cuddleballs snuggle snuggles
snuggling relationship relationships married wedding weddings honeymoon
flirty intimate intimacy attractive attraction chemistry jealous jealousy
straight gay lesbian bisexual bi trans transgender submissive dominant dom
sub fetish kinky kink consent consensual boundaries boundary respect respectful
comfortable uncomfortable safe unsafe private privacy public blocked block
unblock report reported reporting harassment harassing rude creepy creep
accept accepted accepting accepts account across action active add added adding
address adjust adjusted adjusting admit adventure advice although apart appear
appears arm arms arrive arrived arriving attention available avoid awake awful
balance ban banned barefoot begin behind beside best bite biting bites bless
blessed blessing blood blow blushes bottom bounce bouncing breast breath breathe
breathing broke build building built bump bumped button buttons careful caring
catching caught cause cheek cheeks choice choose chose chosen close closed
closely closer closest closing coffee compliment compliments connect connected
connecting connection control controls could've couldn't've count country crush
curious cutey cuteness delicious deserve deserved desk dinner dirty dive diving
dog door downstairs drunk ear ears edit edited editing effect eventually excellent
except expecting explain explained fear finally find finding finger fingers floor
focus forever forgive forgotten frozen further future gentle gently glitch glitches
glitchy grab grabbing ground had hadn't half happiness harder hardest hate hated
hates hazel health healthy height hour hours huge human humans hundred hurt hurting
imagine impressed incredible inside instead interest internet introduce island item
items jacket jeans jewelry juice jump jumping keyboard kind kindness knee knees lap
laptop laughed laughter learning learnt learned length license lie lies lying listen
listened listening load loaded loading location loose loud lower lunch machine mad
magical main manual match matches matters meaning member members memory minute
minutes mistake mobile monitor morning motion mouse movie movies myth neither
nervous newspaper nickname notification notifications obviously offer offered
offline online opinion option options order otherwise owned pants password past
peace peaceful pet pets petting photo photos photograph photography pick picked
picking pillow plan planned planning platform plugin prefer present press pressed
pressing price prices priority problem problems promise promised proof properly
protect protected pull pulled pulling push pushed pushing random reach receive
received receiving recent recently reconnect reliable remove removed removing
repair request requested requesting require reset resizing restart restarted
restarting return returned returning ride riding ring rings rock round ruin ruined
rush save saved saving search searching secret sec secs section selection select
selected selecting sense separate server servers service session settings setup
shake shaking silent silence size sizes slowly smooth softer soft solid solve
solved space spending spent spread stable stairs step steps stomach strange
stranger stretch stretching strong stronger stunning succeed successful suggest
suggested suggestion support supported surprise surprised switch switched switching
system tag tags taste tasty teeth text texts thick thigh thighs thin thread throat
tight tighter tip tips tongue top trouble truly trust trusted truth try tried
trying turn turned turning twenty two type typed typing underneath unlock unlocked
unlocks unused upstairs vacation version versions video videos visit visited
visiting volume wall walls weather web website weight wet whatcha whenever wherever
whisper whispered whispering whole whom whose wild window windows wing wings
within woke women woman wood word words worn worries worry worrying worth wow yay
yeah yee yeses zoomed zooming hottie hotties hawt soo sooo soooo yesss yessss heyyyy
hii hiii hiiii byee byeee luv luvs luvly y'all c'mon ma'am o'clock should've
would've might've must've
""".split())

# Shared adjectives and technical vocabulary still need English context.
SHARED_ADDITIONS = frozenset("""
adorable bento error ai adult alarm bar calm chat chic coffee contact creator
cruel detail energy extra familiar fantastic final formal global ideal important
invisible material natural object official optional personal popular principal
project regular resident romantic simple special stupid topic transparent
universal urgent valid video
""".split())

# Portuguese words, loanwords, abbreviations, and short tokens needing context.
SHARED_WORDS = frozenset("""
a as am an and are at be been being by can chat casual central club color com
de digital do em era eu for gay he hotel in is it la legal local man me menu
mode model music no normal not of on or original para part party pm por pro
real resident residente roleplay rp se second sex sim sl so solo super taxi
te tempo test to total tu u um usa vc virtual visual zero r ur n y b c 2 4
ok okay lol lmao rofl haha hahaha hehe rs kkk kk xd omg slurl tp lm ao bom eep
hud mesh demo alpha omega beta adult bdsm linden lindens pixel pixels
""".split()) | SHARED_ADDITIONS

# These are recognition phrases. The original message still goes to DeepL.
EXTRA_PHRASES = frozenset("""
hot couple
hot couples
sexy couple
cute couple
beautiful couple
nice couple
good job
well done
no way
no rush
no idea
no doubt
no kidding
not bad
not sure
not interested
no more
no one
come on
come in
come back
go ahead
go on
go away
get out
look out
watch out
what else
anything else
so far
so good
so hot
too hot
damn hot
hot af
sexy af
as hell
all set
all done
all yours
all of us
let me know
let me see
let me check
leave me alone
give me a minute
give me a sec
give me a second
long time no see
nice to meet you
nice meeting you
pleased to meet you
you look hot
you look great
you look amazing
you look gorgeous
love your outfit
love your avatar
what do you mean
what does that mean
are you single
are you married
want to dance
wanna dance
want to cuddle
tp me
tp please
tp pls
tp plz
send tp
send me a tp
send lm
send me a lm
can you hear me
can u hear me
on my way
be back soon
back in a bit
afk a bit
need to relog
got disconnected
voice chat
local chat
im me
dm me
pm me
u r
u ok
u okay
ty vm
ty so much
tyvm
thx a lot
thankyou
goodnight
goodmorning
goodbye
sup
wassup
whassup
howdy
hiya
heya
hai
heyy
heyyy
nah
nahh
nooo
u 2
4 u
yup
yass
yea
yeah
yess
aww
awww
awwww
oops
ouch
yikes
yummy
yum
smh
fml
ily
ilysm
ic
ikr
fr
omfg
lmfao
wtf
wth
stfu
idgaf
fwb
wb
cu
cya
cu later
see u
miss u
love u
luv u
i luv u
i luv you
ily too
how r u
r u ok
r u there
r u single
where r u
how old r u
what r u doing
u look hot
ur hot
ur cute
ur sexy
ur welcome
it's ok
its ok
it's okay
its okay
is ok
is okay
np at all
ofc i do
""".strip().splitlines())

# Evidence against the vocabulary fallback, especially mixed PT/EN messages.
# This is not a complete Portuguese detector; langid remains the general fallback.
PORTUGUESE_HINTS = frozenset("""
oi ola olá sim nao não talvez obrigado obrigada valeu bom boa bons boas bem
tudo voce você voces vocês vc vcs eu estou esta está estamos estava tava ta tá
sou somos tenho tem temos tinha tinha meu minha meus minhas seu sua seus suas
nos nós nosso nossa nossas nossos dele dela ele ela eles elas você vc ué
que qual quem como onde quando quanto porque pq tambem também muito muita
muitos muitas mais menos mas hoje ontem amanhã amanha agora depois antes
aqui ali ai aí la lá então entao isso isto esse essa este esta essas esses
nesse nessa nisso neste nesta aquele aquela aquilo pra pro para com sem pelo
pela pelos pelas por uma um uns umas de da das dos do no na nos nas num numa
ao aos e é foi ser sera será se so só ate até ja já ne né nem fez fazer
faz fala falar falo falou disse diz dizer vou vai vamos ir pode posso podemos
pode poderia quero quer queremos queria preciso precisa preciso ver viu vejo
gosto gostei gosto gosto amo amor linda lindo lindos lindas casal casais
quente gostoso gostosa gostosos gostosas bonita bonito bonitas bonitos roupa
avatarzinho saudade saudades beijo beijos abraco abraço abracos abraços
dançar dancar dança danca bora vem vem vem daqui comigo contigo vocezinha
trabalho trabalhando casa noite tarde dia dias gente pessoa pessoas coisa
manda mandar mandou envio enviar enviou posso consigo consegui deu dar tira
tirar coloca colocar colocou relogar caiu travou cheio cheia
coisas mesmo mesma verdade entendi entender certo certeza desculpa desculpe
legal bacana beleza beleza legal kkk rsrs kkkkk kkkkkk tchau obg blz vlw tb
tbm q eh hj amanha dps agr kd cade cadê poxa aff opa bah vish oxe nossa
""".split())
