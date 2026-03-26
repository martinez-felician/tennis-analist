// --- State ---
let loggedInUsername = 'Player';
let isPremium = false;
let isAuthenticated = false;

const PHASE_LABELS = {
  'friendly':    'Friendly',
  'round-robin': 'Round Robin',
  'quarters':    'Quarterfinals',
  'semis':       'Semifinals',
  'final':       'Final',
};
let matchConfig = { playerName: 'Player', opponentName: 'Opponent', clubName: '', phase: 'friendly', sets: 3, gamesPerSet: 6, deuce: true, tiebreak: true, finalSetTiebreak: false, tiebreakLength: 7, startServing: true };
let inTiebreak = false;
let matchOver = false;
let matchStarted = false;
let isServing = true;
let currentServeType = null;
let tiebreakPointCount = 0;
let servingBeforeTiebreak = true;

let player1Points = 0;
let player2Points = 0;
let player1Games = 0;
let player2Games = 0;
let player1Sets = 0;
let player2Sets = 0;
let currentOutcome = null;
let pointHistory = [];

let stats = {
  // wins
  ace: 0, 'fh-win': 0, 'bh-win': 0, vol: 0, oh: 0, drop: 0, 'opp-err': 0,
  // losses
  df: 0, 'fh-ue': 0, 'bh-ue': 0, 'fh-fe': 0, 'bh-fe': 0, 'opp-win': 0,
  // serve & return
  serve1stIn: 0, serve1stOut: 0, serve2ndIn: 0, returnWon: 0, returnLost: 0,
  // return-specific
  'miss-return': 0,
  // net / touch errors
  'vol-err': 0, 'oh-err': 0, 'drop-err': 0
};

const WIN_METHODS = [
  { key: 'ace',     emoji: '⚡', label: 'Ace' },
  { key: 'fh-win',  emoji: '💪', label: 'Forehand Winner' },
  { key: 'bh-win',  emoji: '🎯', label: 'Backhand Winner' },
  { key: 'vol',     emoji: '🏐', label: 'Volley Winner' },
  { key: 'oh',      emoji: '💥', label: 'Overhead / Smash' },
  { key: 'drop',    emoji: '🪄', label: 'Drop Shot' },
  { key: 'opp-err', emoji: '🤦', label: 'Opponent Error' },
];

const LOSS_METHODS = [
  { key: 'df',           emoji: '⚡', label: 'Double Fault' },
  { key: 'miss-return',  emoji: '🎾', label: 'Miss Return' },
  { key: 'fh-ue',        emoji: '❌', label: 'Forehand Unforced Error' },
  { key: 'bh-ue',        emoji: '❌', label: 'Backhand Unforced Error' },
  { key: 'fh-fe',        emoji: '💨', label: 'Forehand Forced Error' },
  { key: 'bh-fe',        emoji: '💨', label: 'Backhand Forced Error' },
  { key: 'opp-win',      emoji: '🏆', label: 'Opponent Winner' },
  { key: 'vol-err',      emoji: '🏐', label: 'Missed Volley' },
  { key: 'oh-err',       emoji: '💥', label: 'Missed Overhead' },
  { key: 'drop-err',     emoji: '🪄', label: 'Missed Drop Shot' },
];

// --- Practice Plan Data ---
const DRILLS = {
  'df': {
    sessionTitle: 'Serve Consistency',
    items: [
      {
        name: 'Second Serve Zone Targeting',
        duration: '20 min',
        desc: 'Hit 10 serves to each zone (T, body, wide) on both sides. Focus on spin and placement, not pace.',
        cue: 'Aim for 70% of max pace. A ball in play is always better than a double fault.',
      },
      {
        name: 'Kick Serve Build-Up',
        duration: '15 min',
        desc: 'Start with half-speed kick serves and gradually increase. Focus on brushing up the back of the ball for heavy topspin.',
        cue: 'Toss slightly behind your head. Snap your wrist upward at contact.',
      },
      {
        name: 'Pressure Serve Simulation',
        duration: '10 min',
        desc: 'Have a partner call out pressure scores (30-40, deuce). Serve only second serves and track your percentage.',
        cue: 'Establish a pre-serve routine. Breathe and reset before every ball.',
      },
      {
        name: 'Flat Serve + Second Serve Combo',
        duration: '15 min',
        desc: 'Hit a flat first serve and immediately follow with a kick second serve. Focus on a full mental reset between the two.',
        cue: 'When the first serve misses, exhale and reset. The second serve is its own motion — do not rush it.',
      },
      {
        name: 'Serve Box Target Challenge',
        duration: '10 min',
        desc: 'Place a towel in each of the three service zones (T, body, wide). Hit 5 second serves to each zone and count your hits.',
        cue: 'Placement beats pace every time. Know where you are serving before you toss.',
      },
    ],
  },
  'fh-ue': {
    sessionTitle: 'Forehand Consistency',
    items: [
      {
        name: 'Crosscourt Forehand Rally',
        duration: '20 min',
        desc: 'Rally crosscourt forehand-to-forehand with a partner. Goal: 20 consecutive balls without an error.',
        cue: 'Watch the ball all the way to your strings. Keep your swing compact and controlled.',
      },
      {
        name: 'Forehand Target Drill',
        duration: '15 min',
        desc: 'Place a cone 1 meter inside the baseline and sideline. Hit 50 forehands targeting that zone.',
        cue: 'Aim 1 meter over the net for a safety margin. Depth and consistency beat pace.',
      },
      {
        name: 'Shadow Swing Focus',
        duration: '10 min',
        desc: 'Shadow swing without a ball, focusing on a low-to-high swing path and a full follow-through over your shoulder.',
        cue: 'Check your contact point — it should be in front of your body, not beside you.',
      },
      {
        name: 'High-to-Low Swing Reset',
        duration: '10 min',
        desc: 'Slow-motion forehand swings focusing on a low-to-high path. Start at knee height and finish above your shoulder every rep.',
        cue: 'Gravity pulls the ball down — brush up through it to keep it in. Every net error is a swing path issue.',
      },
      {
        name: 'Inside-Out Consistency Run',
        duration: '15 min',
        desc: 'Have a partner feed balls to your forehand corner. Hit inside-out forehands to the opponent backhand side 30 times. No errors — aim wide and deep.',
        cue: 'A ball in play is worth more than a risky winner. Get comfortable hitting with margin.',
      },
    ],
  },
  'bh-ue': {
    sessionTitle: 'Backhand Control',
    items: [
      {
        name: 'Backhand Consistency Rally',
        duration: '20 min',
        desc: 'Rally backhand-to-backhand crosscourt. Track your longest streak and try to beat it each round.',
        cue: 'Keep your non-dominant hand on the throat of the racket until the last moment to stay compact.',
      },
      {
        name: 'Slice Backhand Safety Shot',
        duration: '15 min',
        desc: 'Practice the slice backhand as a reset shot. Hit 30 slices deep down the middle when off balance.',
        cue: 'The slice is your safety valve — use it to buy time and reset the point.',
      },
      {
        name: 'Backhand Wall Rally',
        duration: '10 min',
        desc: 'Hit backhands against a wall, maintaining a consistent rhythm for 2 minutes at a time.',
        cue: 'Focus on a compact backswing. Consistency comes from simplicity.',
      },
      {
        name: 'Backhand High-Ball Drill',
        duration: '15 min',
        desc: 'Have a partner feed high, heavy balls to your backhand. Step back early and loop the ball crosscourt with heavy topspin.',
        cue: 'Step back, absorb, and loop. The high ball is not a threat if you position early and use topspin to neutralize it.',
      },
      {
        name: 'Two-Handed Drive Isolation',
        duration: '10 min',
        desc: 'Hit 50 two-handed backhands focusing only on contact point. Contact should be in front of your hip, not beside it.',
        cue: 'Late contact = errors. Early contact = control. Get in front of the ball every single time.',
      },
    ],
  },
  'fh-fe': {
    sessionTitle: 'Forehand Under Pressure',
    items: [
      {
        name: 'Wide Ball Recovery Drill',
        duration: '20 min',
        desc: 'Have a partner feed wide forehands. Reach the ball in balance and recover to the center after every shot.',
        cue: 'Use a defensive lob or crosscourt angle when stretched — never go for a winner from a bad position.',
      },
      {
        name: 'On-the-Run Forehand',
        duration: '15 min',
        desc: 'Set up cones to run around and hit forehands from various positions. Simulate being pushed wide repeatedly.',
        cue: 'Load onto your outside leg before swinging. Never swing while off balance.',
      },
      {
        name: 'Defensive Lob Practice',
        duration: '10 min',
        desc: 'Practice hitting high defensive lobs when stretched wide. Aim to land the ball deep in the opponent\'s court.',
        cue: 'A good defensive lob resets the point. It is not a losing shot — it is a smart one.',
      },
      {
        name: 'Balance Beam Forehand',
        duration: '10 min',
        desc: 'Hit forehands from an intentionally narrow stance to train balance. If you lose balance after the shot, your weight transfer is off.',
        cue: 'Weight goes into the shot, then stays grounded. Falling back or sideways means you swung before you were set.',
      },
      {
        name: 'Scramble and Reset',
        duration: '15 min',
        desc: 'Have a partner force you wide with consecutive feeds. After each difficult ball, sprint back to center and reset before the next one.',
        cue: 'Recovery speed is as important as shot quality. Get back to base so you control the next ball.',
      },
    ],
  },
  'bh-fe': {
    sessionTitle: 'Backhand Under Pressure',
    items: [
      {
        name: 'High Ball Backhand Drill',
        duration: '20 min',
        desc: 'Have a partner feed high bouncing balls to your backhand. Practice absorbing pace and redirecting safely.',
        cue: 'Step back early to give yourself room. Use a slice or high looping topspin to neutralize.',
      },
      {
        name: 'Backhand Down the Line',
        duration: '15 min',
        desc: 'Practice the DTL backhand from the backhand corner. This shot relieves pressure and opens the court.',
        cue: 'Disguise it by preparing the same as crosscourt. The change of direction will catch opponents off guard.',
      },
      {
        name: 'Defensive Point Simulation',
        duration: '10 min',
        desc: 'Play out points starting in a defensive backhand position. Focus on staying in the point, not going for winners.',
        cue: 'One more ball than your opponent. Consistency under pressure wins matches.',
      },
      {
        name: 'Backhand Neutralizer Rally',
        duration: '15 min',
        desc: 'When pushed wide or off balance, practice hitting a high looping backhand deep to the center. The goal is to recover the point, not win it.',
        cue: 'Use height and depth as your weapons when under pressure. A deep ball to the center gives you time to recover.',
      },
      {
        name: 'Run-Around Forehand as Backup',
        duration: '10 min',
        desc: 'Practice running around a backhand to hit an inside-out forehand when time allows. Knowing you have this option removes pressure from the backhand.',
        cue: 'The run-around forehand is a weapon, not a cheat. Use it when your backhand is not your friend that day.',
      },
    ],
  },
  'opp-win': {
    sessionTitle: 'Court Positioning & Defense',
    items: [
      {
        name: 'Anticipation & Recovery Drill',
        duration: '20 min',
        desc: 'Have a partner hit to random spots. Read their body and racket early, then recover to center after each shot.',
        cue: 'Watch the opponent\'s shoulder rotation — it tells you where the ball is going before they hit.',
      },
      {
        name: 'Return of Serve Practice',
        duration: '15 min',
        desc: 'Focus on blocking returns deep down the middle. Do not try to do too much — just get the ball back in play.',
        cue: 'Short backswing, use the opponent\'s pace. Aim for the center strap of the net.',
      },
      {
        name: 'Defensive Baseline Positioning',
        duration: '10 min',
        desc: 'Stand 1 meter behind the baseline when the opponent is dominant. Prioritize depth over pace on every shot.',
        cue: 'A ball returned deep resets the point. A risky winner attempt from defense usually loses it.',
      },
      {
        name: 'Lob Counter Practice',
        duration: '15 min',
        desc: 'When pushed back by opponent winners, practice responding with a high defensive lob. Reset the point rather than attempting a risky pass.',
        cue: 'A passing shot from a bad position loses more points than it wins. The lob gives you time and shifts the pressure.',
      },
      {
        name: 'Wider Return Positioning',
        duration: '10 min',
        desc: 'Stand wider on the baseline to cut off angles. Practice splitting and recovering to center after each shot to reduce the court your opponent can exploit.',
        cue: 'Covering angles is about positioning before the shot, not speed after it. Set up earlier.',
      },
    ],
  },
  'ace': {
    sessionTitle: 'Serve Weaponization',
    items: [
      {
        name: 'Placement Variety Drill',
        duration: '20 min',
        desc: 'Hit serves in a pattern — T, body, wide — on both deuce and ad sides. Work on precision, not pace.',
        cue: 'Varying placement is more effective than adding pace. Keep your opponent guessing.',
      },
      {
        name: 'Topspin First Serve',
        duration: '15 min',
        desc: 'Develop a heavy topspin first serve. It gives pace, a higher net clearance margin, and a nasty bounce.',
        cue: 'Brush from 7 o\'clock to 1 o\'clock across the back of the ball at contact.',
      },
      {
        name: 'Body Serve Drill',
        duration: '15 min',
        desc: 'Practice serving directly at the opponent\'s body from both sides. A body serve jams the return and creates easy put-away opportunities.',
        cue: 'The body serve is underused at every level. Mix it in with T and wide to keep returners guessing.',
      },
      {
        name: 'Flat Serve Extension Session',
        duration: '15 min',
        desc: 'Hit 20 flat first serves to the T on the deuce side. Focus on a clean toss, full extension, and pronation through contact.',
        cue: 'Extension and pronation generate pace — not arm speed alone. Stretch tall and snap through the ball.',
      },
      {
        name: 'Serve Pattern Sequences',
        duration: '10 min',
        desc: 'Plan and execute 3-serve sequences: e.g. wide + T + body. Mix your serves so the returner cannot settle into a read.',
        cue: 'Predictable servers get attacked. A returner who guesses wrong loses 30%+ more points.',
      },
    ],
  },
  'fh-win': {
    sessionTitle: 'Forehand Aggression',
    items: [
      {
        name: 'Inside-Out Forehand Drill',
        duration: '20 min',
        desc: 'Run around your backhand to hit inside-out forehands to the opponent\'s backhand corner. A pattern that creates free points.',
        cue: 'Set up the shot with a deep crosscourt ball, then attack the next short ball inside-out.',
      },
      {
        name: 'Forehand Approach Shot',
        duration: '15 min',
        desc: 'Practice hitting a deep forehand and following it to the net to finish with a volley.',
        cue: 'Approach down the line to narrow the opponent\'s angle. Move forward as you hit.',
      },
      {
        name: 'Short Ball Attack Drill',
        duration: '15 min',
        desc: 'Have a partner feed short balls to your forehand side. Step in and attack with pace to the open court. Finish the point in 2 shots.',
        cue: 'Short ball = opportunity. Take it early, move forward into the shot, and be aggressive with your target.',
      },
      {
        name: 'Forehand Rally then Attack',
        duration: '15 min',
        desc: 'Rally 4 balls crosscourt, then attack with a forehand winner on the 5th. Build consistency before aggression.',
        cue: 'Set up with patience then attack. Do not go for the winner too early — earn the right shot first.',
      },
      {
        name: 'Forehand Passing Shot',
        duration: '10 min',
        desc: 'Practice forehand passing shots from the baseline when the partner rushes the net. Use a low fast ball down the line or a topspin dip crosscourt.',
        cue: 'The passing shot is won by trajectory — keep it low over the net so the volley cannot be attacked easily.',
      },
    ],
  },
  'bh-win': {
    sessionTitle: 'Backhand Offense',
    items: [
      {
        name: 'Backhand Down the Line Attack',
        duration: '20 min',
        desc: 'Pull the trigger on the DTL backhand winner when given a short ball. Set up crosscourt first, then attack.',
        cue: 'Weight forward, full swing, follow through across your body. Commit fully to the shot.',
      },
      {
        name: 'Heavy Crosscourt Pattern',
        duration: '15 min',
        desc: 'Hit 2-3 deep heavy topspin backhands crosscourt to open the court, then redirect DTL for the winner.',
        cue: 'Build the point first. Do not go DTL from a neutral position — earn it.',
      },
      {
        name: 'Backhand Inside-In Drill',
        duration: '15 min',
        desc: 'Set up in the backhand corner and practice hitting inside-in backhand winners at a sharp angle across the court.',
        cue: 'Inside-in from the backhand side surprises opponents leaning crosscourt. Use it when they are out of position.',
      },
      {
        name: 'Backhand Passing Shot',
        duration: '10 min',
        desc: 'Practice backhand passes when a partner rushes the net. Target the open court low and fast, or lob if they crowd.',
        cue: 'Decide early: down the line if they drift, lob if they crowd the net. Do not wait until the last moment.',
      },
      {
        name: 'Backhand Chip and Charge',
        duration: '15 min',
        desc: 'Chip a backhand slice approach down the line and follow to net. Finish with a volley. A classic pattern that surprises opponents.',
        cue: 'The chip approach works because of the bounce, not pace. Slice it deep and low, then move in.',
      },
    ],
  },
  'vol': {
    sessionTitle: 'Net Game Development',
    items: [
      {
        name: 'Volley Reflex Drill',
        duration: '20 min',
        desc: 'Stand at the service line while a partner feeds rapid volleys alternating left and right. Use compact punches.',
        cue: 'No backswing on volleys. Redirect with your wrist firm and use the opponent\'s pace.',
      },
      {
        name: 'Serve & Volley Pattern',
        duration: '15 min',
        desc: 'Serve and immediately charge the net. Hit the first volley deep, then put away the second volley.',
        cue: 'Split step as the opponent hits their return. This gives you balance to move in any direction.',
      },
      {
        name: 'Low Volley Pick-Up',
        duration: '15 min',
        desc: 'Have a partner feed low dipping balls at your feet. Practice lifting these safely, deep to the center.',
        cue: 'Bend your knees, not your back. The low volley is all about getting down to the ball and lifting with an open racket face.',
      },
      {
        name: 'Half-Volley Control Drill',
        duration: '10 min',
        desc: 'Stand at the service line and practice half-volleys — balls that bounce right at your feet. Use a soft wrist and redirect deep.',
        cue: 'The half-volley is a reaction shot. Keep the racket face open and absorb the ball — do not force it.',
      },
      {
        name: 'Drop Volley Touch',
        duration: '10 min',
        desc: 'Practice absorbing pace and dropping the ball just over the net with backspin. Partner feeds medium-pace balls from the baseline.',
        cue: 'Soften your grip at impact. The drop volley is the most touch-dependent shot in tennis — you have to feel it.',
      },
    ],
  },
  'oh': {
    sessionTitle: 'Overhead Confidence',
    items: [
      {
        name: 'Overhead Target Practice',
        duration: '20 min',
        desc: 'Have a partner lob repeatedly. Move back quickly and hit overheads to open areas of the court.',
        cue: 'Point at the ball with your non-racket hand as it rises — this sets your position perfectly.',
      },
      {
        name: 'Jump Overhead Drill',
        duration: '15 min',
        desc: 'Practice the jump overhead for deep lobs. Jump off your dominant foot and snap down at contact.',
        cue: 'Do not wait for the ball to drop too low. Meet it at the highest point you can comfortably reach.',
      },
      {
        name: 'Deep Lob — Smash or Bounce Decision',
        duration: '10 min',
        desc: 'Train yourself to read when a lob is too deep and let it bounce, then hit a topspin reply instead of forcing a jumping smash.',
        cue: 'A safe topspin off the bounce beats a shanked jumping overhead. Know your limit and play within it.',
      },
      {
        name: 'Scissors-Jump Overhead',
        duration: '15 min',
        desc: 'Practice the scissors jump for balls behind you. Load on the front foot, scissor your legs in the air, and snap down at contact.',
        cue: 'The scissors jump gives you stability in the air. Load on the front foot before you jump — never fall backwards.',
      },
      {
        name: 'Overhead Placement Drill',
        duration: '15 min',
        desc: 'Have a partner lob to both sides while you aim overheads at specific zones — crosscourt and down the line. Placement over power.',
        cue: 'An overhead you aim is worth three you smash blindly. Pick your spot before the ball reaches you.',
      },
    ],
  },
  'drop': {
    sessionTitle: 'Touch & Disguise',
    items: [
      {
        name: 'Drop Shot Disguise Drill',
        duration: '20 min',
        desc: 'Hit 5 regular groundstrokes then execute a drop shot with identical preparation. Disguise is everything.',
        cue: 'The preparation must look identical to a regular shot. Only change what happens at the moment of contact.',
      },
      {
        name: 'Drop Shot + Follow-In',
        duration: '15 min',
        desc: 'Hit a drop shot and immediately charge the net to put away the opponent\'s desperate reply.',
        cue: 'The drop shot is a setup shot — always be ready to finish at the net.',
      },
      {
        name: 'Backhand Drop Shot Precision',
        duration: '15 min',
        desc: 'Practice the backhand drop shot from rally. Prepare like a slice and deaden the ball just over the net. Aim for it to bounce twice before the service line.',
        cue: 'The backhand drop is harder to disguise, so set it up off a neutral rally — not when running.',
      },
      {
        name: 'Drop Shot from Mid-Court',
        duration: '10 min',
        desc: 'Practice drop shots from inside the baseline. The closer you are, the shorter it needs to land and the less time your opponent has.',
        cue: 'Position makes the drop shot lethal. Move in first, then surprise.',
      },
      {
        name: 'Drop-Lob Combination',
        duration: '10 min',
        desc: 'Hit a drop shot, let the opponent sprint in, then lob their reply over them. A devastating 1-2 combination.',
        cue: 'Watch for your opponent\'s desperate reply. If it is short or high, the lob over them is almost always on.',
      },
    ],
  },
  'opp-err': {
    sessionTitle: 'Consistency & Pressure',
    items: [
      {
        name: 'Heavy Topspin Baseline Drill',
        duration: '20 min',
        desc: 'Hit heavy topspin balls deep to your opponent\'s backhand consistently. Make them miss from discomfort.',
        cue: 'Aim 1 meter inside the baseline. Consistency + depth = opponent errors.',
      },
      {
        name: 'Crosscourt Pressure Pattern',
        duration: '15 min',
        desc: 'Rally crosscourt with heavy topspin until a short ball appears, then change direction aggressively.',
        cue: 'Be patient. Let the opponent make the mistake instead of forcing things.',
      },
      {
        name: 'Deep Ball Depth Drill',
        duration: '15 min',
        desc: 'Rally with the goal of landing every ball within 1 meter of the baseline. Mark the zone with cones. Depth is your weapon.',
        cue: 'Deep balls push your opponent back and create shorter replies. Depth beats pace as a forcing tool.',
      },
      {
        name: 'High Topspin Spin-Rate Rally',
        duration: '10 min',
        desc: 'Rally focusing on maximum topspin without power. A heavy ball at shoulder height is more uncomfortable than a flat one.',
        cue: 'Brush steeply up through the ball. It should climb, then drop fast past the baseline.',
      },
    ],
  },
  'miss-return': {
    sessionTitle: 'Return of Serve',
    items: [
      {
        name: 'Block Return Drill',
        duration: '20 min',
        desc: 'Stand just inside the baseline and practice short, compact block returns deep down the middle. Use the server\'s pace — no full swing.',
        cue: 'Short backswing. Meet the ball early and redirect it. Getting it back in play beats going for a winner.',
      },
      {
        name: 'Return Placement Targets',
        duration: '15 min',
        desc: 'Place cones at the T and wide zones. Return serves aiming for each target alternately. Focus on depth over pace.',
        cue: 'Pick your target before the serve lands. Commit to it — late decisions cause shanks and misses.',
      },
      {
        name: 'Split-Step Timing',
        duration: '10 min',
        desc: 'Practice the split step as the server tosses. Land and explode toward the ball. Good timing is the foundation of a reliable return.',
        cue: 'Split step as the racket makes contact with the ball. Too early or too late and you will be late on every return.',
      },
      {
        name: 'Chip-and-Charge Return',
        duration: '10 min',
        desc: 'Practice chipping the return short and following to the net. Works especially well against a slow second serve.',
        cue: 'The chip return is controlled aggression. Aim it short and low, then use your net position to win the point.',
      },
      {
        name: 'Aggressive Return Attack',
        duration: '15 min',
        desc: 'Take the second serve early and drive it deep crosscourt or down the line. Step inside the baseline to take it on the rise.',
        cue: 'Taking the ball early removes the server\'s recovery time. Stand closer in and commit to an early contact point.',
      },
    ],
  },
  'vol-err': {
    sessionTitle: 'Volley Reliability',
    items: [
      {
        name: 'Close-Range Volley Exchange',
        duration: '20 min',
        desc: 'Stand at the service line with a partner doing the same. Exchange volleys continuously, keeping the ball in play. Focus on compact punches with a firm wrist.',
        cue: 'No backswing. The volley is a punch, not a swing. Use the incoming pace and redirect.',
      },
      {
        name: 'Feed and Volley Approach',
        duration: '15 min',
        desc: 'Have a partner feed short balls. Move forward, hit a deep volley, and recover to the net position for a finish. Repeat 20 times.',
        cue: 'Stay low on the approach. Bend your knees — volleying upright kills your control.',
      },
      {
        name: 'Pressure Volley Simulation',
        duration: '10 min',
        desc: 'Play points starting at the net. Focus on keeping the first volley deep and the second volley away. Don\'t go for winners too early.',
        cue: 'The first volley is about control and depth, not the winner. Set it up with the second.',
      },
      {
        name: 'Touch Volley Minitennis',
        duration: '10 min',
        desc: 'Both players at the net, play out points with soft volleys only. No power — all placement, angles, and touch.',
        cue: 'Minitennis at the net sharpens feel instantly. No backswing, no power — just wrist firmness and redirection.',
      },
      {
        name: 'First Volley Depth Target',
        duration: '15 min',
        desc: 'After serving and rushing the net, hit every first volley as deep and central as possible. Use a cone 1 meter inside the baseline as your target.',
        cue: 'The first volley is about control and positioning for the second. Depth to the center is always the safest play.',
      },
    ],
  },
  'oh-err': {
    sessionTitle: 'Overhead Execution',
    items: [
      {
        name: 'Lob and Smash Drill',
        duration: '20 min',
        desc: 'Have a partner lob repeatedly from the baseline. Move back quickly, position under the ball, and smash to open areas of the court.',
        cue: 'Point at the ball with your free hand as it rises — this automatically sets your footwork and shoulder turn.',
      },
      {
        name: 'Footwork-First Overhead',
        duration: '15 min',
        desc: 'Practise moving back using small crossover steps before hitting. The most common overhead error is poor positioning, not a bad swing.',
        cue: 'Get behind the ball, not under it. Contact should be slightly in front of your body, not directly above your head.',
      },
      {
        name: 'Deep Lob Recovery',
        duration: '10 min',
        desc: 'When the lob is too deep to smash, practice turning and hitting a topspin ball off the bounce rather than forcing a difficult overhead.',
        cue: 'Know when to let it bounce. A safe topspin reply is better than a shanked overhead on the retreat.',
      },
      {
        name: 'Sun Drill',
        duration: '10 min',
        desc: 'Practice overhead tracking when looking into a bright sky. Use a hat in training to simulate tough conditions.',
        cue: 'If you cannot track the ball against the sky, let it bounce. A safe recovery ball beats a shanked overhead every time.',
      },
      {
        name: 'Overhead Footwork Ladder',
        duration: '15 min',
        desc: 'Use an agility ladder to work on the crossover step pattern for overhead setup. Move back, split, and recover forward after each rep.',
        cue: 'The footwork is the overhead. If you are not behind the ball, even a perfect swing will produce an error.',
      },
    ],
  },
  'drop-err': {
    sessionTitle: 'Drop Shot Execution',
    items: [
      {
        name: 'Touch Drill at the Net',
        duration: '15 min',
        desc: 'Stand just behind the service line and practice soft, sliced drop shots that land just over the net with backspin. Aim to bounce twice before the service line.',
        cue: 'Open the racket face and slide under the ball. Less pace than you think — let the slice do the work.',
      },
      {
        name: 'Drop Shot From Rally',
        duration: '20 min',
        desc: 'Rally crosscourt and execute a drop shot on the 5th ball. The preparation must look identical to a normal groundstroke — disguise is everything.',
        cue: 'If your opponent can read it before you hit it, they will run it down every time. Disguise first, touch second.',
      },
      {
        name: 'Drop Shot and Follow-In',
        duration: '10 min',
        desc: 'After every drop shot, immediately move to the net to put away the reply. A drop shot that you don\'t follow in gives your opponent time to recover.',
        cue: 'Hit and move. The drop shot is a setup shot — you must finish the point at the net.',
      },
      {
        name: 'Approach then Drop',
        duration: '15 min',
        desc: 'Approach the net with a deep groundstroke, wait for the reply, then hit a drop volley to finish. A two-shot combination.',
        cue: 'The drop volley after an approach surprises opponents expecting a strong finish. Give them the opposite.',
      },
      {
        name: 'Net Tape Challenge',
        duration: '10 min',
        desc: 'Hang a string 10 cm above the net. Practice drop shots that clear the net with minimum margin and maximum backspin.',
        cue: 'The tighter your clearance, the shorter the bounce. But never sacrifice clearance for spin — hitting the net loses the point.',
      },
    ],
  },
};

// --- Drill rotation tracking (localStorage) ---
// Each drill is tracked as "shotKey:drillIndex" → count of times shown.
// A drill is skipped once it has been shown 2 times; when all drills for a key
// are maxed out, that key's counts reset so the cycle restarts.

function _getDrillCounts() {
  try { return JSON.parse(localStorage.getItem('ta-drill-counts') || '{}'); }
  catch (e) { return {}; }
}

function _saveDrillCounts(counts) {
  try { localStorage.setItem('ta-drill-counts', JSON.stringify(counts)); }
  catch (e) {}
}

function _availableDrills(shotKey) {
  const all    = (DRILLS[shotKey] || {}).items || [];
  const counts = _getDrillCounts();
  let available = all.filter((_, i) => (counts[`${shotKey}:${i}`] || 0) < 2);
  if (available.length === 0) {
    // All maxed — reset this key and return everything
    const updated = { ...counts };
    all.forEach((_, i) => { delete updated[`${shotKey}:${i}`]; });
    _saveDrillCounts(updated);
    available = all;
  }
  return available;
}

function _commitDrills(shotKey, drills) {
  const all    = (DRILLS[shotKey] || {}).items || [];
  const counts = _getDrillCounts();
  drills.forEach(drill => {
    const idx = all.findIndex(d => d.name === drill.name);
    if (idx >= 0) {
      const k = `${shotKey}:${idx}`;
      counts[k] = (counts[k] || 0) + 1;
    }
  });
  _saveDrillCounts(counts);
}

function generatePracticePlan(weaknesses, strengths) {
  const sessions = [];
  let day = 1;

  // Top 1 weakness — show all available drills (rotation-filtered)
  if (weaknesses.length > 0) {
    const w    = weaknesses[0];
    const data = DRILLS[w.key];
    if (data) {
      const drills = _availableDrills(w.key);
      _commitDrills(w.key, drills);
      const mins = drills.reduce((s, d) => s + parseInt(d.duration), 0);
      sessions.push({ day: day++, type: 'weakness', title: data.sessionTitle, sub: `Fix: ${w.label} — ${w.count}x this match`, drills, mins });
    }
  }

  // Top 1 strength — show all available drills (rotation-filtered)
  if (strengths.length > 0) {
    const s    = strengths[0];
    const data = DRILLS[s.key];
    if (data) {
      const drills = _availableDrills(s.key);
      _commitDrills(s.key, drills);
      const mins = drills.reduce((sum, d) => sum + parseInt(d.duration), 0);
      sessions.push({ day: day++, type: 'strength', title: data.sessionTitle, sub: `Develop: ${s.label} — ${s.count}x this match`, drills, mins });
    }
  }

  sessions.push({
    day: day,
    type: 'match',
    title: 'Match Simulation',
    sub: 'Apply this week\'s techniques in practice sets',
    drills: [
      { name: 'Warm-Up Rally', duration: '15 min', desc: 'Slow crosscourt rally focusing on footwork and consistency. No winners.', cue: 'This is preparation, not competition. Get your timing right.' },
      { name: 'Practice Sets', duration: '60 min', desc: 'Play practice sets consciously using the patterns you drilled this week.', cue: 'Focus on the process, not the score. Did you execute the drills in a real point?' },
    ],
    mins: 75,
  });

  return sessions;
}

function analyzePerformance(statsData) {
  const s = statsData || stats;
  const totalPoints = Object.values(s).reduce((t, v) => t + v, 0);
  if (totalPoints < 5) return null;

  const strengths = WIN_METHODS
    .map(m => ({ ...m, count: s[m.key] || 0 }))
    .filter(m => m.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 1);

  const weaknesses = LOSS_METHODS
    .map(m => ({ ...m, count: s[m.key] || 0 }))
    .filter(m => m.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 1);

  return { strengths, weaknesses };
}

// Cache so switching tabs doesn't re-generate the plan and re-burn drill counts
let _insightCache = null;  // { statsHash, html }

function _statsHash(s) { return JSON.stringify(s); }

async function renderInsights() {
  const emptyEl   = document.getElementById('insights-empty');
  const contentEl = document.getElementById('insights-content');

  // Try current match first; fall back to all-time stats if not enough data
  let insightStats = stats;
  let insightSource = null;   // null = current match, number = match count
  const currentTotal = Object.values(stats).reduce((s, v) => s + v, 0);

  if (currentTotal < 5 && isAuthenticated) {
    try {
      const res     = await fetch('/api/matches');
      const matches = await res.json();
      if (matches.length > 0) {
        // Free users: last 2 matches; premium: all matches
        const pool   = isPremium ? matches : matches.slice(0, 2);
        const merged = {};
        pool.forEach(m => {
          try {
            const s = JSON.parse(m.stats);
            Object.keys(s).forEach(k => { merged[k] = (merged[k] || 0) + (s[k] || 0); });
          } catch (e) {}
        });
        insightStats  = merged;
        insightSource = pool.length;
      }
    } catch (e) {}
  }

  const result = analyzePerformance(insightStats);

  if (!result) {
    emptyEl.style.display   = 'flex';
    contentEl.style.display = 'none';
    return;
  }

  emptyEl.style.display   = 'none';
  contentEl.style.display = 'flex';

  const totalPoints = Object.values(insightStats).reduce((s, v) => s + v, 0);
  const sourceLabel = insightSource !== null
    ? `Across your last ${insightSource} match${insightSource !== 1 ? 'es' : ''}`
    : 'This match';

  const summaryHTML = `
    <div class="plan-summary">
      <div class="plan-summary-title">${sourceLabel} · ${totalPoints} points</div>
      ${result.weaknesses.map(w => `<div class="plan-summary-row"><span class="insight-badge red">Weakness</span>${w.emoji} ${w.label} — ${w.count}x</div>`).join('')}
      ${result.strengths.map(s  => `<div class="plan-summary-row"><span class="insight-badge green">Strength</span>${s.emoji} ${s.label} — ${s.count}x</div>`).join('')}
    </div>
  `;

  if (!isPremium) {
    contentEl.innerHTML = summaryHTML + `
      <div class="match-card-locked">
        <span class="lock-icon">🔒</span>
        <div>
          <strong>Practice Plan — Premium only</strong>
          <p>Upgrade to get a personalized multi-day drill plan built around your weaknesses.</p>
        </div>
        <button class="upgrade-btn" onclick="window.location.href='/profile'">Upgrade — $7/mo</button>
      </div>
    `;
    return;
  }

  // Only generate a new plan (and commit drill counts) when the underlying stats change
  const currentHash = _statsHash(insightStats);
  if (_insightCache && _insightCache.statsHash === currentHash) {
    contentEl.innerHTML = summaryHTML + _insightCache.planHTML;
    return;
  }

  const plan = generatePracticePlan(result.weaknesses, result.strengths);

  const planHTML = plan.map(s => `
    <div class="plan-session ${s.type}">
      <div class="plan-session-header">
        <div class="plan-day">Day ${s.day}</div>
        <div class="plan-session-info">
          <div class="plan-session-title">${s.title}</div>
          <div class="plan-session-sub">${s.sub}</div>
        </div>
        <div class="plan-duration">${s.mins} min</div>
      </div>
      <div class="plan-drills">
        ${s.drills.map(d => `
          <div class="drill-card">
            <div class="drill-header">
              <span class="drill-time">${d.duration}</span>
              <span class="drill-name">${d.name}</span>
            </div>
            <p class="drill-desc">${d.desc}</p>
            <div class="drill-cue"><span class="drill-cue-icon">💡</span><span>${d.cue}</span></div>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');

  _insightCache = { statsHash: currentHash, planHTML };
  contentEl.innerHTML = summaryHTML + planHTML;
}

// --- Navigation ---
function switchView(view, force) {
  // Warn if user navigates away from tracker mid-match (not for programmatic calls)
  if (!force && matchStarted && !matchOver && view !== 'tracker') {
    if (!confirm('You have a match in progress. Stats and Insights are still visible — your match will continue when you return to Tracker.')) return;
  }
  document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('view-' + view).classList.add('active');
  document.getElementById('nav-' + view).classList.add('active');

  const setupEl = document.getElementById('view-setup');
  if (view === 'tracker') {
    // Re-show setup screen only if no match is running
    if (setupEl && !matchStarted) setupEl.style.display = 'flex';
  } else {
    // Stats / Insights — always hide setup so they're immediately accessible
    if (setupEl) setupEl.style.display = 'none';
  }

  if (view === 'stats') {
    // Default to all-time tab when no match is running; stay on current tab mid-match
    const tab = matchStarted ? currentStatsTab : 'all';
    switchStatsTab(tab);
  }
  if (view === 'insights') renderInsights();
}

// --- Step 1: Outcome ---
function selectOutcome(won) {
  currentOutcome = won;
  let methods = won ? [...WIN_METHODS] : [...LOSS_METHODS];
  if (won) {
    if (!isServing) methods = methods.filter(m => m.key !== 'ace');
  } else {
    // df is handled by the Double Fault button in step-0, never comes through here
    methods = methods.filter(m => m.key !== 'df');
    // miss-return is only valid when returning
    if (isServing) methods = methods.filter(m => m.key !== 'miss-return');
  }
  const grid = document.getElementById('method-grid');
  grid.innerHTML = '';
  methods.forEach(m => {
    const btn = document.createElement('button');
    btn.className = 'method-btn ' + (won ? 'win-method' : 'lose-method');
    btn.onclick = () => selectMethod(m.key);
    btn.innerHTML = `<span class="method-emoji">${m.emoji}</span><span class="method-label">${m.label}</span>`;
    grid.appendChild(btn);
  });
  document.getElementById('step2-title').textContent = won ? 'How did you win it?' : 'How did you lose it?';
  document.getElementById('step-1').classList.remove('active');
  document.getElementById('step-2').classList.add('active');
}

// --- XSS sanitization ---
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// --- State snapshot helpers ---
function captureState() {
  pointHistory.push({
    p1Points: player1Points, p2Points: player2Points,
    p1Games:  player1Games,  p2Games:  player2Games,
    p1Sets:   player1Sets,   p2Sets:   player2Sets,
    inTiebreak, tiebreakPointCount, isServing,
    servingBeforeTiebreak, matchOver,
    stats: { ...stats },
  });
}

function persistState() {
  if (!matchStarted || matchOver) return;
  try {
    localStorage.setItem('ta-match-state', JSON.stringify({
      matchConfig,
      player1Points, player2Points,
      player1Games,  player2Games,
      player1Sets,   player2Sets,
      inTiebreak, tiebreakPointCount, isServing,
      servingBeforeTiebreak, matchOver, matchStarted,
      stats,
    }));
  } catch (e) {
    // Storage quota exceeded or private browsing — silently ignore
  }
}

function restoreState() {
  const raw = localStorage.getItem('ta-match-state');
  if (!raw) return false;
  try {
    const s = JSON.parse(raw);
    Object.assign(matchConfig, s.matchConfig);
    player1Points = s.player1Points; player2Points = s.player2Points;
    player1Games  = s.player1Games;  player2Games  = s.player2Games;
    player1Sets   = s.player1Sets;   player2Sets   = s.player2Sets;
    inTiebreak = s.inTiebreak;
    tiebreakPointCount = s.tiebreakPointCount;
    isServing = s.isServing;
    servingBeforeTiebreak = s.servingBeforeTiebreak;
    matchOver = s.matchOver;
    matchStarted = s.matchStarted;
    Object.keys(stats).forEach(k => { stats[k] = 0; });
    Object.assign(stats, s.stats);
    return true;
  } catch (e) { return false; }
}

function undoLastPoint() {
  if (!pointHistory.length) { showToast('Nothing to undo.'); return; }
  const s = pointHistory.pop();
  player1Points = s.p1Points; player2Points = s.p2Points;
  player1Games  = s.p1Games;  player2Games  = s.p2Games;
  player1Sets   = s.p1Sets;   player2Sets   = s.p2Sets;
  inTiebreak = s.inTiebreak;
  tiebreakPointCount = s.tiebreakPointCount;
  isServing = s.isServing;
  servingBeforeTiebreak = s.servingBeforeTiebreak;
  matchOver = s.matchOver;
  Object.keys(stats).forEach(k => { stats[k] = 0; });
  Object.assign(stats, s.stats);
  if (!matchOver) {
    const saveBtn = document.getElementById('save-btn');
    if (saveBtn) saveBtn.style.display = 'none';
  }
  persistState();
  updateScore();
  updateStats();
  showInitialStep();
  showToast('Last point undone.');
}

// --- Step 2: Back ---
function goBack() {
  document.getElementById('step-2').classList.remove('active');
  document.getElementById('step-1').classList.add('active');
  document.getElementById('step1-back-row').style.display = isServing ? 'block' : 'none';
}

// --- Step 2: Method ---
function selectMethod(key) {
  captureState();
  stats[key] = (stats[key] || 0) + 1;

  if (isServing) {
    if (currentServeType === '1st') {
      stats.serve1stIn++;
    } else if (currentServeType === '2nd') {
      stats.serve1stOut++; // 1st serve faulted → 2nd serve went in
      stats.serve2ndIn++;
    }
  } else {
    if (currentOutcome) { stats.returnWon++; } else { stats.returnLost++; }
  }

  currentServeType = null;
  addPoint(currentOutcome);
  showInitialStep();
  persistState();
}

// --- Scoring ---
function addPoint(playerWon) {
  if (matchOver) return;
  if (playerWon) { player1Points++; } else { player2Points++; }

  if (inTiebreak) {
    tiebreakPointCount++;
    if (tiebreakPointCount % 2 === 1) { isServing = !isServing; }
  }

  checkGameWinner();
  updateScore();
}

function checkGameWinner() {
  const p1 = player1Points;
  const p2 = player2Points;

  if (inTiebreak) {
    const len = matchConfig.tiebreakLength;
    if (p1 >= len && p1 - p2 >= 2) { winTiebreak(true); }
    else if (p2 >= len && p2 - p1 >= 2) { winTiebreak(false); }
    return;
  }

  if (!matchConfig.deuce) {
    if (p1 >= 4) { winGame(true); }
    else if (p2 >= 4) { winGame(false); }
    return;
  }

  if (p1 >= 4 && p1 - p2 >= 2) { winGame(true); }
  else if (p2 >= 4 && p2 - p1 >= 2) { winGame(false); }
}

function winGame(playerWon) {
  if (playerWon) { player1Games++; } else { player2Games++; }
  player1Points = 0;
  player2Points = 0;
  isServing = !isServing; // serve alternates each game
  checkSetWinner();
}

function checkSetWinner() {
  const g = matchConfig.gamesPerSet;
  const isLastSet = (player1Sets + player2Sets) === matchConfig.sets - 1;

  if (player1Games === g && player2Games === g) {
    if (matchConfig.tiebreak && (!isLastSet || matchConfig.finalSetTiebreak)) {
      servingBeforeTiebreak = isServing;
      inTiebreak = true;
      tiebreakPointCount = 0;
      isServing = !isServing; // returner serves first in tiebreak
      player1Points = 0;
      player2Points = 0;
      showToast('Tie-break!');
    }
    return;
  }

  if (player1Games >= g && player1Games - player2Games >= 2) { winSet(true); }
  else if (player2Games >= g && player2Games - player1Games >= 2) { winSet(false); }
}

function winSet(playerWon) {
  if (playerWon) { player1Sets++; } else { player2Sets++; }
  player1Games = 0;
  player2Games = 0;
  const name = playerWon ? matchConfig.playerName : 'Opponent';
  showToast(name + ' won the set!');
  checkMatchWinner(playerWon);
}

function winTiebreak(playerWon) {
  inTiebreak = false;
  tiebreakPointCount = 0;
  isServing = servingBeforeTiebreak; // original server starts next set
  if (playerWon) { player1Sets++; } else { player2Sets++; }
  player1Games = 0;
  player2Games = 0;
  player1Points = 0;
  player2Points = 0;
  const name = playerWon ? matchConfig.playerName : 'Opponent';
  showToast(name + ' won the set!');
  checkMatchWinner(playerWon);
}

function checkMatchWinner(playerWon) {
  const needed = Math.ceil(matchConfig.sets / 2);
  if ((playerWon ? player1Sets : player2Sets) >= needed) {
    matchOver = true;
    const name = playerWon ? matchConfig.playerName : 'Opponent';
    showToast(name + ' won the match!');
    showSaveButton();
    setTimeout(() => switchView('stats', true), 2500);
  }
}

function getPointDisplay(p1, p2) {
  if (inTiebreak) {
    return p1 + ' \u2013 ' + p2;
  }
  const labels = [0, 15, 30, 40];
  if (!matchConfig.deuce && p1 >= 3 && p2 >= 3) {
    return '40 \u2013 40';
  }
  if (p1 >= 3 && p2 >= 3) {
    if (p1 === p2) return 'Deuce';
    return p1 > p2 ? 'Advantage You' : 'Advantage Opponent';
  }
  return (labels[p1] ?? 40) + ' \u2013 ' + (labels[p2] ?? 40);
}

function updateScore() {
  document.getElementById('sets').textContent = player1Sets + ' \u2013 ' + player2Sets;
  document.getElementById('games').textContent = player1Games + ' \u2013 ' + player2Games;
  document.getElementById('points').textContent = getPointDisplay(player1Points, player2Points);

  const statusEl = document.getElementById('serve-status');
  const statusTextEl = document.getElementById('serve-status-text');
  if (statusEl && statusTextEl) {
    statusTextEl.textContent = isServing ? 'Serving' : 'Returning';
    statusEl.className = 'serve-status ' + (isServing ? 'serving' : 'returning');
  }
}

// --- Stats ---
let currentStatsTab = 'match';

function updateStats(statsData) {
  const s = statsData || stats;

  const won  = Object.entries(s).filter(([k]) => WIN_METHODS.some(m => m.key === k)).reduce((a, [, v]) => a + v, 0);
  const lost = Object.entries(s).filter(([k]) => LOSS_METHODS.some(m => m.key === k)).reduce((a, [, v]) => a + v, 0);
  const total   = won + lost;
  const winrate = total > 0 ? Math.round((won / total) * 100) : null;

  document.getElementById('stat-won').textContent      = won;
  document.getElementById('stat-lost').textContent     = lost;
  document.getElementById('stat-winrate').textContent  = winrate !== null ? winrate + '%' : '\u2014';
  document.getElementById('winrate-bar').style.width   = (winrate ?? 0) + '%';

  // Reset all shot-type cells to 0 before filling
  document.querySelectorAll('[id^="s-"]').forEach(el => {
    if (!['s-serve1-pct', 's-serve2-pct', 's-return-pct'].includes(el.id)) el.textContent = '0';
  });
  Object.keys(s).forEach(key => {
    const el = document.getElementById('s-' + key);
    if (el) el.textContent = s[key];
  });

  const s1Total  = (s.serve1stIn || 0) + (s.serve1stOut || 0);
  const s2Total  = (s.serve2ndIn || 0) + (s.df || 0);
  const retTotal = (s.returnWon  || 0) + (s.returnLost  || 0);
  document.getElementById('s-serve1-pct').textContent = s1Total  > 0 ? Math.round(((s.serve1stIn || 0) / s1Total)  * 100) + '%' : '—';
  document.getElementById('s-serve2-pct').textContent = s2Total  > 0 ? Math.round(((s.serve2ndIn || 0) / s2Total)  * 100) + '%' : '—';
  document.getElementById('s-return-pct').textContent = retTotal > 0 ? Math.round(((s.returnWon  || 0) / retTotal) * 100) + '%' : '—';
}

async function switchStatsTab(tab) {
  currentStatsTab = tab;
  document.getElementById('tab-this-match').classList.toggle('active', tab === 'match');
  document.getElementById('tab-all-matches').classList.toggle('active', tab === 'all');

  const saveBtn  = document.getElementById('save-btn');
  const resetBtn = document.querySelector('.reset-btn');
  const lockEl   = document.getElementById('stats-all-lock');

  if (tab === 'match') {
    document.getElementById('stats-title').textContent       = 'Match Statistics';
    document.getElementById('stats-match-count').textContent = '';
    if (saveBtn)  saveBtn.style.display  = matchOver ? 'block' : 'none';
    if (resetBtn) resetBtn.style.display = 'block';
    if (lockEl)   lockEl.style.display   = 'none';
    updateStats();
    return;
  }

  // All Matches tab
  document.getElementById('stats-title').textContent       = 'All-Time Statistics';
  document.getElementById('stats-match-count').textContent = 'Loading…';
  if (saveBtn)  saveBtn.style.display  = 'none';
  if (resetBtn) resetBtn.style.display = 'none';
  if (lockEl)   lockEl.style.display   = 'none';

  try {
    const res     = await fetch('/api/matches');
    const matches = await res.json();

    if (!matches.length) {
      document.getElementById('stats-match-count').textContent = 'No saved matches yet';
      updateStats({});
      return;
    }

    if (!isPremium) {
      // Free users: preview stats from the 2 most recent matches only
      const preview = matches.slice(0, 2);
      const merged  = {};
      preview.forEach(m => {
        try {
          const s = JSON.parse(m.stats);
          Object.keys(s).forEach(k => { merged[k] = (merged[k] || 0) + (s[k] || 0); });
        } catch (e) {}
      });
      const locked = matches.length - preview.length;
      document.getElementById('stats-match-count').textContent =
        `Preview: ${preview.length} of ${matches.length} match${matches.length !== 1 ? 'es' : ''}`;
      updateStats(merged);
      if (lockEl && locked > 0) {
        lockEl.innerHTML = `
          <div class="match-card-locked">
            <span class="lock-icon">🔒</span>
            <div>
              <strong>${locked} more match${locked !== 1 ? 'es' : ''} not included</strong>
              <p>Upgrade to Premium to see your full all-time statistics across all matches.</p>
            </div>
            <button class="upgrade-btn" onclick="window.location.href='/profile'">Upgrade — $7/mo</button>
          </div>
        `;
        lockEl.style.display = 'block';
      }
      return;
    }

    const merged = {};
    matches.forEach(m => {
      try {
        const s = JSON.parse(m.stats);
        Object.keys(s).forEach(k => { merged[k] = (merged[k] || 0) + (s[k] || 0); });
      } catch (e) {}
    });

    const n = matches.length;
    document.getElementById('stats-match-count').textContent = `Across ${n} match${n !== 1 ? 'es' : ''}`;
    updateStats(merged);
  } catch (e) {
    document.getElementById('stats-match-count').textContent = 'Could not load matches';
  }
}

// --- Toast ---
let toastTimer = null;
function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.add('show');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}

// --- Setup ---
function selectOpt(btn) {
  const group = btn.closest('[data-group]').dataset.group;
  btn.closest('[data-group]').querySelectorAll('.setup-opt').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (group === 'tiebreak') {
    const hasTiebreak = btn.dataset.value === 'yes';
    document.getElementById('field-finalset').style.display = hasTiebreak ? 'flex' : 'none';
    document.getElementById('field-tblength').style.display = 'none';
  }
  if (group === 'finalset') {
    document.getElementById('field-tblength').style.display = btn.dataset.value === 'tiebreak' ? 'flex' : 'none';
  }
}

function startMatch() {
  const getVal = group => document.querySelector(`.setup-opts[data-group="${group}"] .setup-opt.active`)?.dataset.value;

  matchConfig.playerName      = loggedInUsername;
  matchConfig.opponentName    = (document.getElementById('setup-opponent')?.value.trim()) || 'Opponent';
  matchConfig.clubName        = (document.getElementById('setup-club')?.value.trim())     || '';
  matchConfig.phase           = getVal('phase') || 'friendly';
  matchConfig.sets            = parseInt(getVal('sets')) || 3;
  matchConfig.gamesPerSet     = parseInt(getVal('games')) || 6;
  matchConfig.deuce           = getVal('deuce') !== 'no';
  matchConfig.tiebreak        = getVal('tiebreak') !== 'no';
  matchConfig.finalSetTiebreak = getVal('finalset') === 'tiebreak';
  matchConfig.tiebreakLength  = parseInt(getVal('tblength')) || 7;
  matchConfig.startServing    = getVal('role') !== 'returning';

  isServing = matchConfig.startServing;
  matchStarted = true;
  document.getElementById('scoreboard-player').textContent   = matchConfig.playerName;
  document.getElementById('scoreboard-opponent').textContent = matchConfig.opponentName;
  document.getElementById('view-setup').style.display = 'none';
  updateScore();
  showInitialStep();
}

function selectServe(type) {
  if (type === 'df') {
    // Double fault: 1st serve faulted, 2nd serve faulted — point lost immediately
    captureState();
    stats.df = (stats.df || 0) + 1;
    stats.serve1stOut++;
    currentServeType = null;
    addPoint(false);
    showInitialStep();
    persistState();
    return;
  }
  currentServeType = type;
  document.getElementById('step-0').classList.remove('active');
  document.getElementById('step-1').classList.add('active');
  document.getElementById('step1-back-row').style.display = 'block';
}

function goBackToServe() {
  currentServeType = null;
  document.getElementById('step-1').classList.remove('active');
  document.getElementById('step-0').classList.add('active');
  document.getElementById('step1-back-row').style.display = 'none';
}

function showInitialStep() {
  document.getElementById('step-2').classList.remove('active');
  document.getElementById('step-1').classList.remove('active');
  document.getElementById('step-0').classList.remove('active');
  document.getElementById('step1-back-row').style.display = 'none';
  if (isServing) {
    document.getElementById('step-0').classList.add('active');
  } else {
    document.getElementById('step-1').classList.add('active');
  }
}

// --- Reset ---
function resetMatch() {
  if (!confirm('Reset the match? All data will be lost.')) return;
  const saveBtn  = document.getElementById('save-btn');
  const notesEl  = document.getElementById('match-notes');
  if (saveBtn)  saveBtn.style.display  = 'none';
  if (notesEl)  { notesEl.style.display = 'none'; notesEl.value = ''; }
  player1Points = 0; player2Points = 0;
  player1Games = 0;  player2Games = 0;
  player1Sets = 0;   player2Sets = 0;
  inTiebreak = false;
  matchOver = false;
  isServing = true;
  currentServeType = null;
  tiebreakPointCount = 0;
  Object.keys(stats).forEach(k => { stats[k] = 0; });

  // Deactivate all steps
  document.getElementById('step-0').classList.remove('active');
  document.getElementById('step-1').classList.remove('active');
  document.getElementById('step-2').classList.remove('active');

  updateScore();
  updateStats();

  // Reset setup screen defaults
  document.querySelectorAll('.setup-opt').forEach(b => b.classList.remove('active'));
  document.querySelector('.setup-opts[data-group="phase"]   [data-value="friendly"]').classList.add('active');
  document.querySelector('.setup-opts[data-group="sets"]    [data-value="3"]').classList.add('active');
  document.querySelector('.setup-opts[data-group="games"]   [data-value="6"]').classList.add('active');
  document.querySelector('.setup-opts[data-group="deuce"]   [data-value="yes"]').classList.add('active');
  document.querySelector('.setup-opts[data-group="tiebreak"][data-value="yes"]').classList.add('active');
  document.querySelector('.setup-opts[data-group="finalset"][data-value="full"]').classList.add('active');
  document.getElementById('field-finalset').style.display = 'flex';
  document.querySelector('.setup-opts[data-group="tblength"][data-value="7"]').classList.add('active');
  document.querySelector('.setup-opts[data-group="role"]    [data-value="serving"]').classList.add('active');
  document.getElementById('field-tblength').style.display = 'none';
  const oppInput  = document.getElementById('setup-opponent');
  const clubInput = document.getElementById('setup-club');
  matchStarted = false;
  pointHistory = [];
  localStorage.removeItem('ta-match-state');
  if (oppInput)  oppInput.value  = '';
  if (clubInput) clubInput.value = '';
  document.getElementById('view-setup').style.display = 'flex';
  switchView('tracker', true);
}

// --- Auth & Save ---
async function initApp() {
  const res = await fetch('/api/auth/me');
  if (!res.ok) {
    // Anonymous — let them use the tracker freely
    updateNavForAnonymous();
    showOnboardingIfNeeded();
    return;
  }
  isAuthenticated = true;
  const user = await res.json();
  loggedInUsername = user.username || 'Player';
  isPremium = !!user.is_premium;
  const el = document.getElementById('nav-username');
  if (el) el.textContent = '👤 ' + user.username;

  showOnboardingIfNeeded();

  // Auto-save any match that was interrupted by session expiry or saved-before-signup
  const pending = localStorage.getItem('pendingMatch');
  if (pending) {
    localStorage.removeItem('pendingMatch');
    try {
      const saveRes = await fetch('/api/matches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: pending,
      });
      if (saveRes.ok) showToast('Your match was saved to your profile!');
      else            showToast('Could not recover previous match — sorry.');
    } catch (e) {
      showToast('Could not recover previous match — sorry.');
    }
  }
}

function updateNavForAnonymous() {
  const menu = document.getElementById('nav-menu');
  if (!menu) return;
  const accountLink = menu.querySelector('a[href="/profile"]');
  if (accountLink) { accountLink.href = '/login'; accountLink.innerHTML = '🔑 Log In / Sign Up'; }
  const logoutBtn = menu.querySelector('.nav-drop-logout');
  if (logoutBtn) logoutBtn.style.display = 'none';
}

// --- Onboarding ---
let onboardingStep = 0;

function showOnboardingIfNeeded() {
  if (localStorage.getItem('ta-onboarded')) return;
  const overlay = document.getElementById('onboarding-overlay');
  if (overlay) overlay.style.display = 'flex';
}

function onboardStep(dir) {
  const totalSteps = 3;
  document.getElementById('ostep-' + onboardingStep).classList.remove('active');
  document.getElementById('odot-'  + onboardingStep).classList.remove('active');
  onboardingStep += dir;

  if (onboardingStep >= totalSteps) {
    localStorage.setItem('ta-onboarded', '1');
    document.getElementById('onboarding-overlay').style.display = 'none';
    return;
  }

  document.getElementById('ostep-' + onboardingStep).classList.add('active');
  document.getElementById('odot-'  + onboardingStep).classList.add('active');
  document.getElementById('onboard-prev').style.visibility = onboardingStep > 0 ? 'visible' : 'hidden';
  document.getElementById('onboard-next').textContent = onboardingStep === totalSteps - 1 ? 'Start Tracking' : 'Next →';
}

async function logoutUser() {
  await fetch('/api/auth/logout', { method: 'POST' });
  window.location.href = '/login';
}

function showSaveButton() {
  const btn   = document.getElementById('save-btn');
  const notes = document.getElementById('match-notes');
  if (btn)   { btn.style.display   = 'block'; btn.disabled = false; btn.textContent = 'Save Match'; }
  if (notes) { notes.style.display = 'block'; notes.value = ''; }
}

async function saveMatch() {
  const btn = document.getElementById('save-btn');
  const notesEl = document.getElementById('match-notes');
  const matchPayload = {
    config: matchConfig,
    stats,
    result: { player1Sets, player2Sets, won: player1Sets > player2Sets },
    notes:  notesEl ? notesEl.value.trim() : '',
  };

  if (!isAuthenticated) {
    localStorage.setItem('pendingMatch', JSON.stringify(matchPayload));
    showToast('Create an account to save your match!');
    btn.textContent = 'Create Account →';
    setTimeout(() => { window.location.href = '/login?pending=1'; }, 1800);
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Saving…';
  const res = await fetch('/api/matches', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(matchPayload),
  });
  if (res.ok) {
    btn.textContent = 'Saved ✓';
    localStorage.removeItem('ta-match-state');
    showToast('Match saved to your profile!');
  } else if (res.status === 401) {
    // Session expired — stash match data so it survives the login redirect
    localStorage.setItem('pendingMatch', JSON.stringify(matchPayload));
    btn.disabled = false;
    btn.textContent = 'Save Match';
    showToast('Session expired — logging you in to save your match…');
    setTimeout(() => { window.location.href = '/login'; }, 2000);
  } else {
    btn.disabled = false;
    btn.textContent = 'Save Match';
    showToast('Failed to save — try again.');
  }
}

// --- Init ---
updateScore();
initApp().then(() => {
  // Restore an interrupted in-progress match
  if (!matchStarted && restoreState()) {
    document.getElementById('scoreboard-player').textContent   = matchConfig.playerName;
    document.getElementById('scoreboard-opponent').textContent = matchConfig.opponentName;
    document.getElementById('view-setup').style.display = 'none';
    updateScore();
    updateStats();
    showInitialStep();
    if (matchOver) showSaveButton();
    showToast('Match restored from last session.');
  }
}).then(() => {
  // Handle deep links from home page quick-access cards
  const params = new URLSearchParams(location.search);
  if (params.get('stats') === 'all') {
    history.replaceState({}, '', '/');
    switchView('stats');
  } else if (params.get('view') === 'insights') {
    history.replaceState({}, '', '/');
    switchView('insights');
  }
});
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js');
