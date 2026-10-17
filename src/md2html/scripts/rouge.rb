require 'json'
require 'rouge'
STDOUT.sync = true
puts JSON.generate(ready: true)
STDIN.each_line do |line|
  begin
    request = JSON.parse(line)
    if request['code']
      lexer = Rouge::Lexer.find(request['language']) || Rouge::Lexers::PlainText
      result = Rouge::Formatters::HTML.new.format(lexer.lex(request['code']))
    else
      result = Rouge::Theme.find(request['style']).new(scope: '.codehilite').render
    end
    puts JSON.generate(value: result)
  rescue => error
    puts JSON.generate(error: error.message)
  end
end
