'use client';

import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../stores/useAppStore';
import { useChapter1Store } from '../stores/useChapter1Store';
import { useChapter2Store } from '../stores/useChapter2Store';
import StarIcon from '../components/icons/StarIcon';
import FindHatTask from '../components/FindHatTask';
import BridgeTask from '../components/BridgeTask';

export default function TownScreen() {
  const navigate = useNavigate();
  const stars = useAppStore((s) => s.stars);
  const currentScene = useChapter1Store((s) => s.currentScene);
  const helpedCharacters = useChapter1Store((s) => s.helpedCharacters);
  const firstChapterComplete = useChapter1Store((s) => s.firstChapterComplete);
  const returnToTown = useChapter1Store((s) => s.returnToTown);
  const closeTease = useChapter1Store((s) => s.closeTease);
  const helpCharacter = useChapter1Store((s) => s.helpCharacter);
  const continueFindHat = useChapter1Store((s) => s.continueFindHat);
  const stones = useChapter1Store((s) => s.stones);
  const hat = useChapter1Store((s) => s.hat);
  const posterPieces = useChapter1Store((s) => s.posterPieces);
  const startIntro = useChapter1Store((s) => s.startIntro);
  const owlHelped = helpedCharacters.includes('owl');
  const introStartedRef = useRef(false);

  const chapter2Available = useChapter2Store((s) => s.chapter2Available);
  const ch2Scene = useChapter2Store((s) => s.currentScene);
  const placedPlanks = useChapter2Store((s) => s.placedPlanks);
  const startBridgeIntro = useChapter2Store((s) => s.startBridgeIntro);
  const activateBridgeTask = useChapter2Store((s) => s.activateBridgeTask);
  const completeBridge = useChapter2Store((s) => s.completeBridge);
  const ch2ReturnToTown = useChapter2Store((s) => s.returnToTown);
  const unlockChapter2 = useChapter2Store((s) => s.unlockChapter2);
  const bridgeOutroShown = useChapter2Store((s) => s.bridgeOutroShown);
  const seenBridgeOutro = useChapter2Store((s) => s.seenBridgeOutro);

  useEffect(() => {
    if (firstChapterComplete && !chapter2Available && ch2Scene === 'idle') {
      unlockChapter2();
    }
  }, [firstChapterComplete, chapter2Available, ch2Scene, unlockChapter2]);

  useEffect(() => {
    if (currentScene === 'townReturn') {
      const timer = setTimeout(() => {
        useChapter1Store.getState().showNextFriendTease();
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [currentScene]);

  useEffect(() => {
    if (currentScene === 'idle' && !firstChapterComplete && !introStartedRef.current) {
      introStartedRef.current = true;
      const timer = setTimeout(() => {
        startIntro();
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [currentScene, firstChapterComplete, startIntro]);

  useEffect(() => {
    if (currentScene === 'intro') {
      const timer = setTimeout(() => {
        useChapter1Store.getState().closeTease();
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [currentScene]);

  const owlDone = helpedCharacters.includes('owl');

  return (
    <div className="relative min-h-[100svh] overflow-hidden bg-[#E9F3FF]">
      {/* 柔光紙張紋理 */}
      <div
        className="pointer-events-none absolute inset-0 opacity-70 mix-blend-multiply"
        style={{
          backgroundImage:
            'radial-gradient(circle at 20% 30%, rgba(255,255,255,0.08) 0%, transparent 45%), radial-gradient(circle at 75% 20%, rgba(218,232,255,0.18) 0%, transparent 60%)',
        }}
      />

      {/* 遠景：天空漸層 + 雲朵 + 遠山 */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-[#D8ECFF] via-[#EEF6FF] to-[#E9F3FF]" />
        <div className="absolute left-10 top-10 h-12 w-28 rounded-full bg-white/60 blur-xl" />
        <div className="absolute right-12 top-14 h-10 w-24 rounded-full bg-white/45 blur-lg" />
        <div className="absolute left-1/3 top-24 h-14 w-36 rounded-full bg-white/35 blur-2xl" />
        <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none" aria-hidden="true">
          <path
            d="M0,120 C90,95 170,104 260,90 C350,76 420,100 520,94 C620,88 740,72 860,88 C960,102 1040,110 1180,98 C1280,92 1360,108 1440,100 L1440,320 L0,320 Z"
            fill="#CDE0F5"
            opacity="0.75"
          />
          <path
            d="M0,180 C130,155 260,175 390,166 C520,157 620,174 750,168 C880,162.12 1010,150.24 1140,155.76 C1260,160.76 1360,172 1440,170 L1440,320 L0,320 Z"
            fill="#B7D2EA"
            opacity="0.65"
          />
        </svg>
      </div>

      {/* 中景：生命之樹/地標 */}
      <div className="pointer-events-none absolute inset-x-0 top-[14%] z-0 flex justify-center">
        <svg width="220" height="260" viewBox="0 0 220 260" fill="none">
          <rect x="92" y="180" width="36" height="56" rx="14" fill="#C4A07A" />
          <rect x="88" y="158" width="44" height="20" rx="10" fill="#A97A52" />
          <circle cx="110" cy="108" r="54" fill="#B6DDC8" />
          <circle cx="80" cy="130" r="34" fill="#C3E8D4" />
          <circle cx="140" cy="130" r="34" fill="#C3E8D4" />
          <circle cx="110" cy="94" r="28" fill="#D6F2E2" />
          <circle cx="110" cy="116" r="12" fill="#F7C56A" opacity="0.8" />
          {(stars > 0 || owlHelped) && (
            <circle cx="110" cy="116" r="24" fill="#F7C56A" opacity="0.18">
              <animate attributeName="r" values="22;32;22" dur="3.6s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.18;0.08;0.18" dur="3.6s" repeatCount="indefinite" />
            </circle>
          )}
          {/* 星星燈籠掛在樹梢 */}
          <g transform="translate(160, 40)">
            <path d="M14 4 L18 14 L28 16 L20 22 L22 32 L14 26 L6 32 L8 22 L0 16 L10 14 Z" fill="#FFD166" />
            <rect x="10" y="34" width="8" height="6" rx="2" fill="#BC6C25" />
            <path d="M6 40 L22 40" stroke="#BC6C25" strokeWidth="2" strokeLinecap="round" />
          </g>
        </svg>
      </div>

      {/* 中景：區域地標 */}
      <div className="pointer-events-none absolute inset-x-0 top-[34%] z-0 flex justify-center gap-10">
        <div className="h-10 w-10 rounded-full border-4 border-[#F6D391] bg-[#FCEBD0]" />
        <div className="h-10 w-10 rounded-full border-4 border-[#A9C8E2] bg-[#EAF4FB]" />
      </div>

      {/* 前景：草地 + 圓石 + 小花 */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute bottom-0 left-0 right-0 h-36 overflow-hidden">
          <svg className="h-full w-full" viewBox="0 0 1440 220" preserveAspectRatio="none">
            <path d="M0,120 C140,100 260,114 400,108 C540,102 640,118 800,110 C960,104 1080,90 1220,102 C1320,110 1400,114 1440,110 L1440,220 L0,220 Z" fill="#E4EED4" />
            <path d="M0,150 C120,140 220,155 360,148 C500,142 640,160 780,152 C920,146 1040,134 1180,144 C1300,152 1400,158 1440,154 L1440,220 L0,220 Z" fill="#D6E2BC" />
            <circle cx="160" cy="176" r="12" fill="#C6D6AE" opacity="0.85" />
            <circle cx="480" cy="168" r="8" fill="#BFCBA2" opacity="0.85" />
            <circle cx="860" cy="180" r="6" fill="#C9D5B5" opacity="0.85" />
            <circle cx="1260" cy="170" r="10" fill="#C2CDA7" opacity="0.85" />
          </svg>
          <div
            className="absolute inset-0 opacity-70"
            style={{
              backgroundImage:
                'radial-gradient(circle at 20% 60%, rgba(247,197,106,0.12) 0%, transparent 40%), radial-gradient(circle at 75% 70%, rgba(235,210,180,0.12) 0%, transparent 50%)',
            }}
          />
        </div>
      </div>

      {/* 星星計數融入場景（右上小燈籠旁） */}
      <div className="absolute right-14 top-12 z-10 flex items-center gap-1">
        <StarIcon size={14} stroke="#E8A83E" />
        <span className="text-[11px] font-bold text-[#4A4A4A]">{stars} 顆星</span>
      </div>

      {/* 角色：星星嚮導 SVG（intro 階段保留） */}
      {currentScene === 'intro' && (
        <div className="pointer-events-none absolute bottom-28 left-6 z-10">
          <svg width="72" height="84" viewBox="0 0 72 84" fill="none">
            <path d="M36 4 L44 24 L66 26 L48 40 L54 62 L36 50 L18 62 L24 40 L6 26 L28 24 Z" fill="#FFCC70" />
            <circle cx="30" cy="32" r="2.6" fill="#4A4A4A" />
            <circle cx="42" cy="32" r="2.6" fill="#4A4A4A" />
            <path d="M31 40 Q36 45 41 40" stroke="#4A4A4A" strokeWidth="2.2" strokeLinecap="round" />
            <path d="M28 18 Q36 10 44 18" stroke="#FFB74D" strokeWidth="2.6" strokeLinecap="round" />
          </svg>
        </div>
      )}

      {/* 家長入口：右下角小木屋（無文字） */}
      <button
        onClick={() => navigate('/game/parent')}
        className="absolute bottom-28 right-5 z-10 flex flex-col items-center gap-1 transition-transform duration-150 hover:scale-105 active:scale-95"
        aria-label="家長入口"
      >
        <svg width="44" height="38" viewBox="0 0 44 38" fill="none">
          <rect x="4" y="18" width="36" height="18" rx="6" fill="#D9A07A" />
          <path d="M1 18 L22 2 L43 18" fill="#7D4A2A" />
          <rect x="17" y="24" width="10" height="12" rx="3" fill="#FCEBD0" />
        </svg>
        <span className="text-[10px] font-bold text-[#4A4A4A]/70">家長</span>
      </button>

      {/* 關係圖譜名牌：爺爺節點狀態（場景內木牌） */}
      <div
        className={`absolute bottom-24 left-5 z-10 flex flex-col items-center gap-1 transition-colors duration-300 ${
          owlDone ? '' : 'opacity-70'
        }`}
        aria-label="關係圖譜"
      >
        <svg width="52" height="64" viewBox="0 0 52 64" fill="none">
          <circle cx="26" cy="26" r="20" fill={owlDone ? '#8B6F5C' : '#D6D6D6'} />
          <circle cx="20" cy="22" r="5" fill={owlDone ? '#FCEBD0' : '#E6E6E6'} />
          <circle cx="32" cy="22" r="5" fill={owlDone ? '#FCEBD0' : '#E6E6E6'} />
          <circle cx="20" cy="22" r="2.5" fill={owlDone ? '#4A4A4A' : '#B0B0B0'} />
          <circle cx="32" cy="22" r="2.5" fill={owlDone ? '#4A4A4A' : '#B0B0B0'} />
          <path
            d="M22 34 Q26 40 30 34"
            stroke={owlDone ? '#4A4A4A' : '#B0B0B0'}
            strokeWidth="2.2"
            strokeLinecap="round"
          />
          <path d="M22 6 Q26 2 30 6" stroke="#F6D391" strokeWidth="3" strokeLinecap="round" />
          <path d="M30 6 Q34 10 36 18" stroke={owlDone ? '#F6D391' : '#D6D6D6'} strokeWidth="2.6" strokeLinecap="round" />
          <path d="M18 6 Q14 10 12 18" stroke={owlDone ? '#F6D391' : '#D6D6D6'} strokeWidth="2.6" strokeLinecap="round" />
          {/* 木牌插桿 */}
          <rect x="23" y="44" width="6" height="16" rx="2" fill="#BC6C25" />
          <circle cx="26" cy="60" r="3" fill="#BC6C25" opacity="0.5" />
        </svg>
        <span className={`text-[10px] font-semibold ${owlDone ? 'text-[#4A4A4A]' : 'text-gray-400'}`}>
          {owlDone ? '爺爺' : '爺爺'}
        </span>
      </div>

      {/* 關係圖譜名牌：大力節點狀態（場景內木牌） */}
      {firstChapterComplete && chapter2Available && (
        <button
          onClick={() => {
            if (ch2Scene === 'idle') startBridgeIntro();
          }}
          className={`absolute bottom-24 left-28 z-10 flex flex-col items-center gap-1 transition-colors duration-300 ${
            ch2Scene === 'completed' ? '' : 'opacity-70'
          }`}
          aria-label="大力節點"
        >
          <svg width="52" height="64" viewBox="0 0 52 64" fill="none">
            <circle cx="26" cy="26" r="20" fill={ch2Scene === 'completed' ? '#8B6F5C' : '#D6D6D6'} />
            <circle cx="20" cy="22" r="5" fill={ch2Scene === 'completed' ? '#FCEBD0' : '#E6E6E6'} />
            <circle cx="32" cy="22" r="5" fill={ch2Scene === 'completed' ? '#FCEBD0' : '#E6E6E6'} />
            <circle cx="20" cy="22" r="2.5" fill={ch2Scene === 'completed' ? '#4A4A4A' : '#B0B0B0'} />
            <circle cx="32" cy="22" r="2.5" fill={ch2Scene === 'completed' ? '#4A4A4A' : '#B0B0B0'} />
            <path
              d="M22 34 Q26 40 30 34"
              stroke={ch2Scene === 'completed' ? '#4A4A4A' : '#B0B0B0'}
              strokeWidth="2.2"
              strokeLinecap="round"
            />
            <path d="M22 6 Q26 2 30 6" stroke="#A9C8E2" strokeWidth="3" strokeLinecap="round" />
            <path d="M30 6 Q34 10 36 18" stroke={ch2Scene === 'completed' ? '#A9C8E2' : '#D6D6D6'} strokeWidth="2.6" strokeLinecap="round" />
            <path d="M18 6 Q14 10 12 18" stroke={ch2Scene === 'completed' ? '#A9C8E2' : '#D6D6D6'} strokeWidth="2.6" strokeLinecap="round" />
            {/* 木牌插桿 */}
            <rect x="23" y="44" width="6" height="16" rx="2" fill="#BC6C25" />
            <circle cx="26" cy="60" r="3" fill="#BC6C25" opacity="0.5" />
          </svg>
          <span className={`text-[10px] font-semibold ${ch2Scene === 'completed' ? 'text-[#4A4A4A]' : 'text-gray-400'}`}>
            {ch2Scene === 'completed' ? '大力' : '大力'}
          </span>
        </button>
      )}

      {/* 爺爺角色站位（idle 階段顯示） */}
      {currentScene === 'idle' && !firstChapterComplete && (
        <button
          onClick={() => {
            const state = useChapter1Store.getState();
            if (state.stones >= 3 && state.hat && state.posterPieces >= 3) {
              state.startCeremony();
            } else {
              state.meetOwl();
            }
          }}
          className="absolute bottom-24 left-1/2 z-20 -translate-x-1/2 flex flex-col items-center gap-1 transition-transform duration-150 hover:scale-105 active:scale-95"
          aria-label="貓頭鷹爺爺求助"
        >
          <svg width="88" height="100" viewBox="0 0 88 100" fill="none">
            {/* 身體 */}
            <rect x="28" y="52" width="32" height="36" rx="12" fill="#8B6F5C" />
            {/* 頭 */}
            <circle cx="44" cy="36" r="28" fill="#8B6F5C" />
            {/* 眼睛 */}
            <circle cx="36" cy="32" r="5" fill="#FCEBD0" />
            <circle cx="52" cy="32" r="5" fill="#FCEBD0" />
            <circle cx="36" cy="32" r="2.5" fill="#4A4A4A" />
            <circle cx="52" cy="32" r="2.5" fill="#4A4A4A" />
            {/* 嘴巴 */}
            <path d="M38 44 Q44 50 50 44" stroke="#4A4A4A" strokeWidth="2.5" strokeLinecap="round" />
            {/* 眼鏡 */}
            <circle cx="36" cy="32" r="8" stroke="#F6D391" strokeWidth="2" fill="none" />
            <circle cx="52" cy="32" r="8" stroke="#F6D391" strokeWidth="2" fill="none" />
            <path d="M44 32 L44 32" stroke="#F6D391" strokeWidth="2" />
            {/* 手 */}
            <path d="M28 60 Q18 66 22 76" stroke="#8B6F5C" strokeWidth="6" strokeLinecap="round" />
            <path d="M60 60 Q70 66 66 76" stroke="#8B6F5C" strokeWidth="6" strokeLinecap="round" />
          </svg>
          <span className="text-base font-bold text-[#4A4A4A] drop-shadow-sm">
            {stones >= 3 && hat && posterPieces >= 3
              ? '來點燈吧'
              : stones > 0 || hat || posterPieces > 0
                ? '繼續冒險'
                : '開始冒險'}
          </span>
          <span className="rounded-full bg-[#FCEBD0] px-3 py-1 text-xs font-bold text-[#8B6F5C]">
            {stones >= 3 && hat && posterPieces >= 3
              ? '材料都齊了'
              : '爺爺需要幫忙'}
          </span>
        </button>
      )}

      {/* 幕 2：爺爺的求助 overlay */}
      {currentScene === 'owlNeedsHelp' && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#2C3E50]/20">
          <div className="flex flex-col items-center gap-4 rounded-3xl border-4 border-[#F6D391] bg-[#FFF8EC] p-6 shadow-xl">
            <p className="text-center text-lg font-bold text-[#4A4A4A]">哎呀！</p>
            <p className="text-center text-base font-bold text-[#4A4A4A]">今晚我要為生命之樹點燈，材料被風吹走了！</p>
            <p className="text-center text-sm text-[#4A4A4A]">幫我撿回 3 顆發亮石頭和我的帽子吧。</p>
            <button
              onClick={() => useChapter1Store.getState().startFindHat()}
              className="rounded-2xl bg-[#F6D391] px-6 py-3 text-base font-bold text-white shadow-sm transition-transform duration-150 hover:scale-105 active:scale-95"
            >
              我去找
            </button>
          </div>
        </div>
      )}

      {/* 幕 3：森林邊任務 */}
      {currentScene === 'findHatTask' && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#2C3E50]/20">
          <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-3xl border-4 border-[#F6D391] bg-[#FFF8EC] p-6 shadow-xl">
            <FindHatTask />
          </div>
        </div>
      )}

      {/* 幕 3.5：橋出現過渡 */}
      {currentScene === 'bridgeAppears' && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#2C3E50]/20">
          <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-3xl border-4 border-[#A9C8E2] bg-[#EAF4FB] p-6 shadow-xl">
            <p className="text-center text-base font-bold text-[#4A4A4A]">木板清理乾淨了</p>
            <p className="text-center text-sm text-[#4A4A4A]">橋出現啦！可以繼續往前走了。</p>
            <svg width="120" height="40" viewBox="0 0 120 40" fill="none" aria-hidden="true">
              <rect x="10" y="16" width="100" height="8" rx="4" fill="#D9A07A" />
              <rect x="18" y="10" width="6" height="20" rx="2" fill="#A97A52" />
              <rect x="50" y="10" width="6" height="20" rx="2" fill="#A97A52" />
              <rect x="82" y="10" width="6" height="20" rx="2" fill="#A97A52" />
            </svg>
            <button
              onClick={continueFindHat}
              className="rounded-2xl bg-[#A9C8E2] px-6 py-3 text-base font-bold text-white shadow-sm transition-transform duration-150 hover:scale-105 active:scale-95"
            >
              繼續
            </button>
          </div>
        </div>
      )}

      {/* 幕 4 & 5：爺爺點燈 ceremony */}
      {currentScene === 'owlThanks' && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#2C3E50]/20">
          <div className="flex flex-col items-center gap-4 rounded-3xl border-4 border-[#F6D391] bg-[#FFF8EC] p-6 shadow-xl">
            <p className="text-center text-lg font-bold text-[#4A4A4A]">啊！第一盞燈亮起來了！</p>
            <p className="text-center text-base font-bold text-[#4A4A4A]">爺爺念完感謝語，燈火從樹梢亮了起來。</p>
            <p className="text-center text-sm text-[#8B6F5C]">小鎮變得越來越溫暖了。</p>
            <button
              onClick={() => {
                helpCharacter('owl');
                returnToTown();
              }}
              className="rounded-2xl bg-[#F6D391] px-6 py-3 text-base font-bold text-white shadow-sm transition-transform duration-150 hover:scale-105 active:scale-95"
            >
              回到小鎮
            </button>
          </div>
        </div>
      )}

      {/* 幕 6 過渡：nextFriendTease（townReturn 後自動彈出） */}
      {currentScene === 'nextFriendTease' && (
        <div className="absolute bottom-24 left-1/2 z-50 w-full max-w-sm -translate-x-1/2 px-4">
          <div className="flex flex-col items-center gap-3 rounded-3xl border-4 border-[#A9C8E2] bg-[#EAF4FB] p-5 shadow-lg">
            {posterPieces < 3 ? (
              <>
                <p className="text-center text-base font-bold text-[#4A4A4A]">爺爺的字條還在語言村，去幫他找回來吧。</p>
                <p className="text-center text-sm text-[#4A4A4A]">把掉的圖卡配對好，他的感謝語就會回來了。</p>
                <button
                  onClick={() => navigate('/game/language')}
                  className="rounded-2xl bg-[#A9C8E2] px-6 py-3 text-base font-bold text-white shadow-sm transition-transform duration-150 hover:scale-105 active:scale-95"
                >
                  去找圖卡
                </button>
              </>
            ) : (
              <>
                <p className="text-center text-base font-bold text-[#4A4A4A]">大力還在池塘邊等著呢。</p>
                <p className="text-center text-sm text-[#4A4A4A]">他的橋還沒修好，暫時沒辦法過來。</p>
              </>
            )}
            <button
              onClick={closeTease}
              className="rounded-2xl bg-white/80 px-5 py-2 text-sm font-bold text-[#4A4A4A] shadow-sm transition-transform duration-150 hover:scale-105 active:scale-95"
            >
              我知道了
            </button>
          </div>
        </div>
      )}

      {/* Chapter 2：大力橋邊介紹 */}
      {ch2Scene === 'bridgeIntro' && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#2C3E50]/20">
          <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-3xl border-4 border-[#A9C8E2] bg-[#EAF4FB] p-6 shadow-xl">
            <p className="text-center text-lg font-bold text-[#4A4A4A]">大力在池塘邊嘆氣</p>
            <p className="text-center text-base font-bold text-[#4A4A4A]">「橋板被風吹走了 3 塊，我沒辦法自己放回去……」</p>
            <p className="text-center text-sm text-[#4A4A4A]">你可以幫我一起把橋板放回原位嗎？</p>
            <button
              onClick={activateBridgeTask}
              className="rounded-2xl bg-[#A9C8E2] px-6 py-3 text-base font-bold text-white shadow-sm transition-transform duration-150 hover:scale-105 active:scale-95"
            >
              我去幫忙
            </button>
          </div>
        </div>
      )}

      {/* Chapter 2：橋板互動 */}
      {ch2Scene === 'bridgeTask' && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#2C3E50]/20">
          <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-3xl border-4 border-[#A9C8E2] bg-[#EAF4FB] p-6 shadow-xl">
            <BridgeTask />
            <button
              onClick={() => {
                if (placedPlanks >= 3) completeBridge();
              }}
              disabled={placedPlanks < 3}
              className={`rounded-2xl px-6 py-3 text-base font-bold text-white shadow-sm transition-transform duration-150 hover:scale-105 active:scale-95 ${
                placedPlanks >= 3 ? 'bg-[#A9C8E2]' : 'bg-gray-300 cursor-not-allowed'
              }`}
            >
              完成了
            </button>
          </div>
        </div>
      )}

      {/* Chapter 2：大力感謝 */}
      {ch2Scene === 'bridgeThanks' && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#2C3E50]/20">
          <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-3xl border-4 border-[#A9C8E2] bg-[#EAF4FB] p-6 shadow-xl">
            <p className="text-center text-lg font-bold text-[#4A4A4A]">謝謝你！</p>
            <p className="text-center text-base font-bold text-[#4A4A4A]">橋現在穩穩當當的了。</p>
            <p className="text-center text-sm text-[#4A4A4A]">大力揮揮手，繼續埋頭工作。</p>
            <button
              onClick={ch2ReturnToTown}
              className="rounded-2xl bg-[#A9C8E2] px-6 py-3 text-base font-bold text-white shadow-sm transition-transform duration-150 hover:scale-105 active:scale-95"
            >
              回到小鎮
            </button>
          </div>
        </div>
      )}

      {/* Chapter 2：返回小鎮提示 */}
      {ch2Scene === 'completed' && !bridgeOutroShown && (
        <div className="absolute top-14 left-1/2 z-40 w-full max-w-md -translate-x-1/2 px-4">
          <div className="flex flex-col items-center gap-3 rounded-3xl border-4 border-[#A9C8E2] bg-[#EAF4FB] p-5 shadow-lg">
            <p className="text-center text-base font-bold text-[#4A4A4A]">橋修好了！大力邀請你下次來參加池塘邊的派對。</p>
            <button
              onClick={seenBridgeOutro}
              className="rounded-2xl bg-white/80 px-5 py-2 text-sm font-bold text-[#4A4A4A] shadow-sm transition-transform duration-150 hover:scale-105 active:scale-95"
            >
              我知道了
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
