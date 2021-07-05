function new_call_obj()
    return setmetatable({}, {
        __call = function()
            lua_tail(0)
        end,
    })
end

function new_close_obj()
    return setmetatable({}, {
        __close = function(self, err)
            new_call_obj()()
        end,
    })
end

function lua_tail(i)
    if i > 2 then
        return lua_c_intermediary()
    end
    return lua_tail(i + 1)
end
